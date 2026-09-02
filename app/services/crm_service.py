"""
CRM Service - n8n Ready

Logs call and booking data to n8n for HubSpot/Salesforce/Pipedrive integration.
Also maintains local JSON log for immediate access.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from app.services.n8n_webhook import n8n_publisher


def _crm_log_path() -> Path:
    """Get the path to the local CRM log file."""
    root = Path(__file__).resolve().parents[1]
    log_path = root / "data" / "crm_log.json"
    log_path.parent.mkdir(exist_ok=True)
    return log_path


def log_call_and_booking(
    client_name: str,
    phone: str,
    property_title: str,
    status: str,
    lead_id: str | None = None,
    session_id: str | None = None,
) -> Dict[str, Any]:
    """
    Log a call and booking to CRM.
    
    Publishes to n8n for HubSpot/Salesforce/Pipedrive sync.
    Also maintains local JSON log for immediate access.
    
    Args:
        client_name: Name of the client
        phone: Phone number
        property_title: Title of the property
        status: Status of the booking
        lead_id: Lead ID in the system
        session_id: Call session ID
        
    Returns:
        Response dict with status and CRM details
    """
    entry = {
        "id": f"crm_{datetime.utcnow().timestamp()}",
        "timestamp": datetime.utcnow().isoformat(),
        "status": status,
        "client_name": client_name,
        "phone": phone,
        "property_title": property_title,
        "lead_id": lead_id,
        "session_id": session_id,
        "synced_at": None,
    }

    # Save to local log
    log_path = _crm_log_path()
    existing = []
    if log_path.exists():
        try:
            existing = json.loads(log_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    existing.append(entry)
    log_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    # Publish to n8n for CRM sync
    crm_payload = {
        "contact": {
            "name": client_name,
            "phone": phone,
        },
        "opportunity": {
            "title": property_title,
            "status": status,
        },
        "lead_id": lead_id,
        "session_id": session_id,
    }
    n8n_event = n8n_publisher.publish("crm_contact_created", crm_payload)
    n8n_status = n8n_event.get("status")

    if n8n_status == "published":
        crm_message = "CRM entry logged locally and synced to HubSpot/Salesforce/Pipedrive via n8n"
    elif n8n_status == "skipped":
        crm_message = "CRM entry logged locally only, n8n CRM webhook is not configured"
    else:
        crm_message = f"CRM entry logged locally only, n8n sync failed: {n8n_event.get('error', n8n_status)}"

    return {
        "id": entry["id"],
        "status": "logged",
        "client_name": client_name,
        "property_title": property_title,
        "local_log": "saved",
        "n8n_status": n8n_status,
        "message": crm_message,
    }


def create_crm_contact(
    client_name: str,
    email: str | None = None,
    phone: str | None = None,
    properties: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Create or update a contact in CRM.
    
    Publishes to n8n for CRM contact creation.
    """
    payload = {
        "contact": {
            "name": client_name,
            "email": email,
            "phone": phone,
        },
        "custom_properties": properties or {},
    }
    n8n_event = n8n_publisher.publish("crm_contact_created", payload)

    return {
        "status": "queued_for_crm",
        "contact_name": client_name,
        "n8n_status": n8n_event.get("status"),
    }


def log_activity(
    lead_id: str,
    activity_type: str,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Log an activity to CRM.
    
    Publishes to n8n for activity logging in CRM system.
    """
    payload = {
        "lead_id": lead_id,
        "activity_type": activity_type,
        "details": details,
        "timestamp": datetime.utcnow().isoformat(),
    }
    n8n_event = n8n_publisher.publish("crm_activity_logged", payload)

    return {
        "status": "queued_for_crm",
        "lead_id": lead_id,
        "activity_type": activity_type,
        "n8n_status": n8n_event.get("status"),
    }


def get_local_crm_log() -> list:
    """Get the local CRM log entries."""
    log_path = _crm_log_path()
    if not log_path.exists():
        return []

    try:
        return json.loads(log_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def clear_local_crm_log() -> bool:
    """Clear the local CRM log."""
    log_path = _crm_log_path()
    if log_path.exists():
        log_path.write_text("[]", encoding="utf-8")
        return True
    return False

