"""
Enhanced Database Store with Full Schema Support

Persists leads, sessions, appointments, followups, and property recommendations
to Postgres using SQLAlchemy ORM with the full production schema.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from sqlalchemy import create_engine, Column, String, DateTime, Text, Boolean, Numeric, ForeignKey, ARRAY, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.models.user import User

from .base import Base


class Lead(Base):
    """Lead record - customer information."""
    __tablename__ = "leads"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    phone_number = Column(String(30), nullable=True)
    customer_name = Column(String(150), nullable=True)
    city = Column(String(100), nullable=True)
    area = Column(String(100), nullable=True)
    budget = Column(String(100), nullable=True)
    property_type = Column(String(50), nullable=True)
    purpose = Column(String(50), nullable=True)
    appointment_interest = Column(Boolean, default=False)
    profile_data = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CallSession(Base):
    """Call session record - conversation metadata."""
    __tablename__ = "call_sessions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id = Column(PG_UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    call_sid = Column(String(150), nullable=True)
    source = Column(String(50), default="vapi")
    transcript = Column(Text, default="")
    intent = Column(String(100), nullable=True)
    status = Column(String(50), default="active")
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)


class PropertyRecommendation(Base):
    """Property recommendation record - properties shown to lead."""
    __tablename__ = "property_recommendations"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(PG_UUID(as_uuid=True), ForeignKey("call_sessions.id"), nullable=True)
    property_id = Column(String(50), nullable=True)
    property_name = Column(String(200), nullable=True)
    city = Column(String(100), nullable=True)
    area = Column(String(100), nullable=True)
    price = Column(Numeric(18, 2), nullable=True)
    recommended_at = Column(DateTime, default=datetime.utcnow)


class Appointment(Base):
    """Appointment record - scheduled property visits."""
    __tablename__ = "appointments"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id = Column(PG_UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    session_id = Column(PG_UUID(as_uuid=True), ForeignKey("call_sessions.id"), nullable=True)
    property_id = Column(String(50), nullable=True)
    property_name = Column(String(200), nullable=True)
    client_name = Column(String(150), nullable=True)
    client_phone = Column(String(30), nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    status = Column(String(50), default="confirmed")
    created_at = Column(DateTime, default=datetime.utcnow)


class Followup(Base):
    """Followup record - scheduled followup tasks."""
    __tablename__ = "followups"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id = Column(PG_UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    session_id = Column(PG_UUID(as_uuid=True), ForeignKey("call_sessions.id"), nullable=True)
    note = Column(Text, nullable=True)
    scheduled_for = Column(DateTime, nullable=True)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


# Database initialization
engine = None
SessionLocal = None

if settings.database_url:
    try:
        # SQLAlchemy 1.4+ no longer accepts the bare 'postgres://' scheme —
        # it must be 'postgresql://' or 'postgresql+psycopg2://'. Normalize.
        db_url = settings.database_url
        if db_url.startswith("postgres://"):
            db_url = "postgresql://" + db_url[len("postgres://"):]
        engine = create_engine(db_url, future=True, pool_pre_ping=True)
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    except Exception as e:
        print(f"Database connection error: {e}")


def init_db():
    """Initialize database tables."""
    if engine is None:
        return False

    try:
        Base.metadata.create_all(bind=engine)
        return True
    except SQLAlchemyError as e:
        print(f"Database init error: {e}")
        return False


def get_session() -> Optional[Session]:
    """Get a database session."""
    if SessionLocal is None:
        return None
    return SessionLocal()


class LeadStore:
    """Operations on Lead table."""

    @staticmethod
    def create_or_update_lead(
        lead_id: str | UUID,
        phone_number: str | None = None,
        customer_name: str | None = None,
        profile: Dict[str, Any] | None = None,
    ) -> Optional[Dict[str, Any]]:
        """Create or update a lead."""
        session = get_session()
        if not session:
            return None

        try:
            lead_uuid = UUID(str(lead_id)) if not isinstance(lead_id, UUID) else lead_id
            existing = session.query(Lead).filter(Lead.id == lead_uuid).first()

            if existing:
                if phone_number:
                    existing.phone_number = phone_number
                if customer_name:
                    existing.customer_name = customer_name
                if profile:
                    existing.profile_data = profile
                    existing.city = profile.get("city")
                    existing.area = profile.get("area")
                    existing.budget = profile.get("budget")
                    existing.property_type = profile.get("property_type")
                    existing.purpose = profile.get("purpose")
                    existing.appointment_interest = profile.get("appointment_interest", False)
                existing.updated_at = datetime.utcnow()
            else:
                lead = Lead(
                    id=lead_uuid,
                    phone_number=phone_number,
                    customer_name=customer_name,
                    city=profile.get("city") if profile else None,
                    area=profile.get("area") if profile else None,
                    budget=profile.get("budget") if profile else None,
                    property_type=profile.get("property_type") if profile else None,
                    purpose=profile.get("purpose") if profile else None,
                    appointment_interest=profile.get("appointment_interest", False) if profile else False,
                    profile_data=profile or {},
                )
                session.add(lead)

            session.commit()
            return {"id": str(existing.id if existing else lead.id), "status": "created_or_updated"}
        except Exception as e:
            session.rollback()
            print(f"Lead store error: {e}")
            return None
        finally:
            session.close()

    @staticmethod
    def fetch_lead(lead_id: str | UUID) -> Optional[Dict[str, Any]]:
        """Fetch a lead by ID."""
        session = get_session()
        if not session:
            return None

        try:
            lead_uuid = UUID(str(lead_id)) if not isinstance(lead_id, UUID) else lead_id
            lead = session.query(Lead).filter(Lead.id == lead_uuid).first()
            if lead:
                return {
                    "id": str(lead.id),
                    "phone_number": lead.phone_number,
                    "customer_name": lead.customer_name,
                    "city": lead.city,
                    "area": lead.area,
                    "budget": lead.budget,
                    "property_type": lead.property_type,
                    "purpose": lead.purpose,
                    "appointment_interest": lead.appointment_interest,
                    "profile": lead.profile_data,
                    "created_at": lead.created_at.isoformat(),
                    "updated_at": lead.updated_at.isoformat(),
                }
            return None
        except Exception as e:
            print(f"Lead fetch error: {e}")
            return None
        finally:
            session.close()


class SessionStore:
    """Operations on CallSession table."""

    @staticmethod
    def create_session(
        lead_id: str | UUID | None = None,
        call_sid: str | None = None,
        source: str = "vapi",
    ) -> Optional[str]:
        """Create a new call session."""
        session = get_session()
        if not session:
            return None

        try:
            call_session = CallSession(
                lead_id=UUID(str(lead_id)) if lead_id else None,
                call_sid=call_sid,
                source=source,
            )
            session.add(call_session)
            session.commit()
            return str(call_session.id)
        except Exception as e:
            session.rollback()
            print(f"Session create error: {e}")
            return None
        finally:
            session.close()

    @staticmethod
    def update_session(
        session_id: str | UUID,
        transcript: str | None = None,
        intent: str | None = None,
        status: str | None = None,
    ) -> bool:
        """Update a call session."""
        session = get_session()
        if not session:
            return False

        try:
            session_uuid = UUID(str(session_id)) if not isinstance(session_id, UUID) else session_id
            call_session = session.query(CallSession).filter(CallSession.id == session_uuid).first()

            if call_session:
                if transcript:
                    call_session.transcript = transcript
                if intent:
                    call_session.intent = intent
                if status:
                    call_session.status = status
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            print(f"Session update error: {e}")
            return False
        finally:
            session.close()

    @staticmethod
    def end_session(session_id: str | UUID) -> bool:
        """Mark a session as completed."""
        session = get_session()
        if not session:
            return False

        try:
            session_uuid = UUID(str(session_id)) if not isinstance(session_id, UUID) else session_id
            call_session = session.query(CallSession).filter(CallSession.id == session_uuid).first()

            if call_session:
                call_session.status = "completed"
                call_session.ended_at = datetime.utcnow()
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            print(f"Session end error: {e}")
            return False
        finally:
            session.close()


class AppointmentStore:
    """Operations on Appointment table."""

    @staticmethod
    def create_appointment(
        lead_id: str | UUID | None,
        session_id: str | UUID | None,
        property_id: str,
        property_name: str,
        client_name: str,
        client_phone: str,
        scheduled_at: datetime | None = None,
        status: str = "confirmed",
    ) -> Optional[str]:
        """Create an appointment."""
        session = get_session()
        if not session:
            return None

        try:
            appointment = Appointment(
                lead_id=UUID(str(lead_id)) if lead_id else None,
                session_id=UUID(str(session_id)) if session_id else None,
                property_id=property_id,
                property_name=property_name,
                client_name=client_name,
                client_phone=client_phone,
                scheduled_at=scheduled_at,
                status=status,
            )
            session.add(appointment)
            session.commit()
            return str(appointment.id)
        except Exception as e:
            session.rollback()
            print(f"Appointment create error: {e}")
            return None
        finally:
            session.close()

    @staticmethod
    def list_appointments(limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent appointments from Postgres."""
        session = get_session()
        if not session:
            return []
        try:
            records = session.query(Appointment).order_by(Appointment.created_at.desc()).limit(limit).all()
            results = []
            for r in records:
                results.append({
                    "appointment_id": str(r.id),
                    "id": str(r.id),
                    "lead_id": str(r.lead_id) if r.lead_id else None,
                    "session_id": str(r.session_id) if r.session_id else None,
                    "property_id": r.property_id or "",
                    "property_title": r.property_name or "",
                    "client_name": r.client_name or "",
                    "client_phone": r.client_phone or "",
                    "scheduled_at": r.scheduled_at.isoformat() if r.scheduled_at else None,
                    "status": r.status or "confirmed",
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                })
            return results
        except Exception as e:
            print(f"Appointment list error: {e}")
            return []
        finally:
            session.close()


class FollowupStore:
    """Operations on Followup table."""

    @staticmethod
    def create_followup(
        followup_id: str | UUID | None = None,
        lead_id: str | UUID | None = None,
        session_id: str | UUID | None = None,
        note: str = "",
        scheduled_for: datetime | str | None = None,
        status: str = "pending",
    ) -> Optional[str]:
        """Create a followup task.
        
        Args:
            followup_id: Optional custom followup ID
            lead_id: Lead identifier
            session_id: Session identifier
            note: Followup note/description
            scheduled_for: When to schedule the followup (datetime or ISO string)
            status: Status of the followup
            
        Returns:
            Followup ID or None on error
        """
        session = get_session()
        if not session:
            return None

        try:
            # Parse scheduled_for if it's a string
            if isinstance(scheduled_for, str):
                scheduled_for = datetime.fromisoformat(scheduled_for.replace('Z', '+00:00'))
            
            followup = Followup(
                id=UUID(str(followup_id)) if followup_id else None,
                lead_id=UUID(str(lead_id)) if lead_id else None,
                session_id=UUID(str(session_id)) if session_id else None,
                note=note,
                scheduled_for=scheduled_for,
                status=status,
            )
            session.add(followup)
            session.commit()
            return str(followup.id)
        except Exception as e:
            session.rollback()
            print(f"Followup create error: {e}")
            return None
        finally:
            session.close()

    @staticmethod
    def get_pending_followups(lead_id: str | UUID | None = None) -> List[Dict[str, Any]]:
        """Get all pending followup tasks."""
        session = get_session()
        if not session:
            return []

        try:
            query = session.query(Followup).filter(Followup.status == "pending")
            if lead_id:
                query = query.filter(Followup.lead_id == UUID(str(lead_id)))

            followups = query.all()
            return [
                {
                    "id": str(f.id),
                    "lead_id": str(f.lead_id) if f.lead_id else None,
                    "note": f.note,
                    "scheduled_for": f.scheduled_for.isoformat() if f.scheduled_for else None,
                    "status": f.status,
                }
                for f in followups
            ]
        except Exception as e:
            print(f"Followup fetch error: {e}")
            return []
        finally:
            session.close()


# Convenience functions
def save_lead_profile(
    lead_id: str,
    profile: Dict[str, Any],
    transcript: str | None = None,
    intent: str | None = None,
) -> bool:
    """Save lead profile to database."""
    return LeadStore.create_or_update_lead(lead_id, profile=profile) is not None


def fetch_lead(lead_id: str) -> Optional[Dict[str, Any]]:
    """Fetch lead from database."""
    return LeadStore.fetch_lead(lead_id)


def create_call_session(lead_id: str | None = None) -> Optional[str]:
    """Create a new call session."""
    return SessionStore.create_session(lead_id)


def end_call_session(session_id: str) -> bool:
    """End a call session."""
    return SessionStore.end_session(session_id)


def create_appointment_record(
    lead_id: str,
    session_id: str,
    property_id: str,
    property_name: str,
    client_name: str,
    client_phone: str,
    scheduled_at: datetime | None = None,
) -> Optional[str]:
    """Create appointment record."""
    return AppointmentStore.create_appointment(
        lead_id, session_id, property_id, property_name, client_name, client_phone, scheduled_at
    )


def create_followup_task(
    lead_id: str,
    session_id: str,
    note: str,
    scheduled_for: datetime,
) -> Optional[str]:
    """Create a followup task."""
    return FollowupStore.create_followup(lead_id, session_id, note, scheduled_for)


def get_pending_followups(lead_id: str | None = None) -> List[Dict[str, Any]]:
    """Get pending followup tasks."""
    return FollowupStore.get_pending_followups(lead_id)
