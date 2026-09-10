"""
Appointment service — creates and manages property visit appointments.

Key changes from the original version:
- Appointment IDs are UUIDs (not sequential), preventing enumeration attacks
- Appointments are linked to lead_id and call_history records
- All datetime operations are timezone-aware (UTC)
- Thread-safe in-memory store with a Lock
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.services import db_store_enhanced
from app.services.call_history import call_history_store

logger = logging.getLogger("appointment_service")
logger.setLevel(logging.INFO)

# In-memory store (lossy on restart — Postgres is the durable store)
appointments: Dict[str, Dict[str, Any]] = {}
_appointments_lock = threading.Lock()


def _parse_dt(value: str) -> datetime:
    """Parse an ISO 8601 string into a timezone-aware datetime (UTC)."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _persist_to_postgres(appointment: Dict[str, Any]) -> None:
    """Best-effort write to Postgres. Never raises — in-memory record is
    already the source of truth for this request."""
    try:
        scheduled_at = _parse_dt(appointment["scheduled_at"])
        postgres_id = db_store_enhanced.AppointmentStore.create_appointment(
            lead_id=appointment.get("lead_id"),
            session_id=appointment.get("session_id"),
            property_id=appointment["property_id"],
            property_name=appointment["property_title"],
            client_name=appointment["client_name"],
            client_phone=appointment["client_phone"],
            scheduled_at=scheduled_at,
            status=appointment["status"],
        )
        if postgres_id:
            appointment["postgres_id"] = postgres_id
    except Exception as e:
        logger.warning(f"[appointment_service] Postgres sync skipped: {e}")


def list_appointments(limit: int = 100, owner_email: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return most recent appointments first (default 100). Filter by owner_email if provided."""
    with _appointments_lock:
        in_memory_items = list(reversed(list(appointments.values())))

    # Query Postgres for durable appointments
    db_items = []
    try:
        db_items = db_store_enhanced.AppointmentStore.list_appointments(limit=limit)
    except Exception as e:
        logger.debug(f"[appointment_service] DB appointment fetch skipped: {e}")

    # Merge by appointment_id / id
    merged = list(in_memory_items)
    seen_ids = {
        item.get("appointment_id") or item.get("id")
        for item in in_memory_items
        if item.get("appointment_id") or item.get("id")
    }

    for db_item in db_items:
        db_id = db_item.get("appointment_id") or db_item.get("id")
        if db_id and db_id not in seen_ids:
            seen_ids.add(db_id)
            merged.append(db_item)

    if owner_email:
        owner_clean = str(owner_email).strip().lower()
        merged = [
            a for a in merged
            if str(a.get("employee_email") or "").strip().lower() == owner_clean 
            or str(a.get("client_email") or "").strip().lower() == owner_clean
            or str(a.get("recipient_email") or "").strip().lower() == owner_clean
        ]
    return merged[:limit]


def validate_appointment_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = ["client_name", "client_phone", "property_id", "property_title", "scheduled_at"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(missing)}")

    try:
        dt = _parse_dt(payload["scheduled_at"])
    except ValueError as exc:
        raise ValueError("scheduled_at must be a valid ISO datetime string.") from exc

    if dt < _now_utc():
        raise ValueError("scheduled_at must be in the future.")

    return {"validated_at": _now_utc().isoformat(), "scheduled_at": dt.isoformat()}


def create_appointment_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    validation = validate_appointment_payload(payload)

    # UUID-based appointment ID — not enumerable
    appointment_id = f"apt-{uuid4().hex[:12]}"

    appointment = {
        "appointment_id": appointment_id,
        "id": appointment_id,
        "lead_id": payload.get("lead_id"),
        "session_id": payload.get("session_id"),
        "client_name": payload["client_name"],
        "client_phone": payload["client_phone"],
        "property_id": payload["property_id"],
        "property_title": payload["property_title"],
        "scheduled_at": validation["scheduled_at"],
        "employee_email": payload.get("employee_email"),
        "recipient_email": payload.get("recipient_email") or payload.get("employee_email"),
        "client_email": payload.get("client_email") or payload.get("employee_email"),
        "status": "confirmed",
        "created_at": validation["validated_at"],
    }
    with _appointments_lock:
        appointments[appointment_id] = appointment
    _persist_to_postgres(appointment)

    # Link call history — record a "confirmed" call entry
    lead_id = payload.get("lead_id") or payload.get("client_phone")
    if lead_id:
        try:
            call_history_store.record_call(
                lead_id=str(lead_id),
                client_phone=payload.get("client_phone"),
                client_name=payload.get("client_name"),
                property_id=payload.get("property_id"),
                property_title=payload.get("property_title"),
                discussed_time=validation["scheduled_at"],
                call_summary="Appointment confirmed via booking API",
                status="confirmed",
            )
        except Exception as e:
            logger.warning(f"[appointment_service] could not link call history: {e}")

    return appointment


def get_appointment(appointment_id: str) -> Optional[Dict[str, Any]]:
    with _appointments_lock:
        return appointments.get(appointment_id)


def reschedule_appointment_record(appointment_id: str, new_time: str) -> Dict[str, Any]:
    with _appointments_lock:
        appointment = appointments.get(appointment_id)
        if not appointment:
            raise ValueError("Appointment not found.")

    try:
        dt = _parse_dt(new_time)
    except ValueError as exc:
        raise ValueError("new_time must be a valid ISO datetime string.") from exc

    if dt < _now_utc():
        raise ValueError("new_time must be in the future.")

    with _appointments_lock:
        appointment["scheduled_at"] = dt.isoformat()
        appointment["status"] = "rescheduled"
    return appointment


def cancel_appointment_record(appointment_id: str) -> Dict[str, Any]:
    with _appointments_lock:
        appointment = appointments.get(appointment_id)
        if not appointment:
            raise ValueError("Appointment not found.")
        appointment["status"] = "cancelled"
    return appointment


def get_appointments_for_lead(lead_id: str) -> List[Dict[str, Any]]:
    """Return all appointments linked to a lead."""
    with _appointments_lock:
        return [a for a in appointments.values() if a.get("lead_id") == lead_id]


def get_appointments_for_phone(phone: str) -> List[Dict[str, Any]]:
    """Return all appointments for a phone number."""
    if not phone:
        return []
    with _appointments_lock:
        return [a for a in appointments.values() if a.get("client_phone") == phone]
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class AppointmentCreate(BaseModel):
    client_name: str = Field(..., description="Name of the client")
    client_phone: str = Field(..., description="Phone number of the client")
    property_id: str = Field(..., description="Identifier of the property")
    property_title: str = Field(..., description="Human readable title of the property")
    scheduled_at: str = Field(..., description="ISO‑8601 datetime string for the appointment")
    employee_email: Optional[str] = Field(None, description="Email of the employee handling the appointment")
    lead_id: Optional[str] = Field(None, description="Related lead identifier, if any")
    session_id: Optional[str] = Field(None, description="Related session identifier, if any")

def create_appointment(appt: AppointmentCreate) -> Dict[str, Any]:
    """Public API used by Vapi service.
    Accepts an AppointmentCreate model, validates payload and creates appointment.
    Returns the persisted appointment dict.
    """
    payload = appt.dict()
    return create_appointment_record(payload)
