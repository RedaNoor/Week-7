from datetime import datetime
from typing import Dict, Any, List

from app.services import db_store_enhanced

appointments: Dict[str, Dict[str, Any]] = {}


def _persist_to_postgres(appointment: Dict[str, Any]) -> None:
    """Best-effort write to Postgres. Never raises, the in-memory record
    created above is already the source of truth for this request."""
    try:
        scheduled_at = datetime.fromisoformat(appointment["scheduled_at"])
        postgres_id = db_store_enhanced.AppointmentStore.create_appointment(
            lead_id=None,
            session_id=None,
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
        print(f"[appointment_service] Postgres sync skipped: {e}")


def list_appointments() -> List[Dict[str, Any]]:
    """Return every appointment created this run, newest first."""
    return list(reversed(list(appointments.values())))


def validate_appointment_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = ["client_name", "client_phone", "property_id", "property_title", "scheduled_at"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(missing)}")

    try:
        dt = datetime.fromisoformat(payload["scheduled_at"])
    except ValueError as exc:
        raise ValueError("scheduled_at must be a valid ISO datetime string.") from exc

    if dt < datetime.now():
        raise ValueError("scheduled_at must be in the future.")

    return {"validated_at": datetime.now().isoformat(), "scheduled_at": dt.isoformat()}


def create_appointment_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    validation = validate_appointment_payload(payload)
    appointment_id = f"apt-{len(appointments) + 1:04d}"
    appointment = {
        "appointment_id": appointment_id,
        "client_name": payload["client_name"],
        "client_phone": payload["client_phone"],
        "property_id": payload["property_id"],
        "property_title": payload["property_title"],
        "scheduled_at": validation["scheduled_at"],
        "employee_email": payload.get("employee_email"),
        "status": "confirmed",
        "created_at": validation["validated_at"],
    }
    appointments[appointment_id] = appointment
    _persist_to_postgres(appointment)
    return appointment


def reschedule_appointment_record(appointment_id: str, new_time: str) -> Dict[str, Any]:
    appointment = appointments.get(appointment_id)
    if not appointment:
        raise ValueError("Appointment not found.")

    try:
        dt = datetime.fromisoformat(new_time)
    except ValueError as exc:
        raise ValueError("new_time must be a valid ISO datetime string.") from exc

    if dt < datetime.now():
        raise ValueError("new_time must be in the future.")

    appointment["scheduled_at"] = dt.isoformat()
    appointment["status"] = "rescheduled"
    return appointment


def cancel_appointment_record(appointment_id: str) -> Dict[str, Any]:
    appointment = appointments.get(appointment_id)
    if not appointment:
        raise ValueError("Appointment not found.")

    appointment["status"] = "cancelled"
    return appointment
