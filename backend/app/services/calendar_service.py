"""
Calendar Service - n8n Ready

Publishes calendar events to n8n for Google Calendar integration.
n8n will handle the actual Google Calendar API call.
"""

from datetime import datetime
from typing import Dict, Any, Optional

from app.services.n8n_webhook import n8n_publisher


def create_calendar_event(
    client_name: str,
    property_title: str,
    scheduled_at: str,
    employee_email: str | None = None,
) -> Dict[str, Any]:
    """
    Create a calendar event.
    
    Publishes to n8n for actual Google Calendar integration.
    Returns a structured response ready for the API caller.
    
    Args:
        client_name: Name of the client
        property_title: Title of the property
        scheduled_at: ISO format datetime
        employee_email: Email of the agent/employee
        
    Returns:
        Response dict with status and event details
    """
    try:
        parsed = datetime.fromisoformat(scheduled_at)
        event_time = parsed.isoformat()
    except (ValueError, TypeError):
        event_time = scheduled_at

    # Create the calendar event payload for n8n
    event_payload = {
        "title": f"Property Visit: {property_title}",
        "description": f"Property visit scheduled for {client_name}",
        "start_time": event_time,
        "attendee_email": employee_email,
        "client_name": client_name,
        "property_title": property_title,
    }

    # Publish to n8n (which will handle actual Google Calendar API call)
    n8n_event = n8n_publisher.publish("calendar_event_created", event_payload)
    n8n_status = n8n_event.get("status")

    if n8n_status == "published":
        status, message = "queued_for_calendar", "Calendar event queued for n8n Google Calendar integration"
    elif n8n_status == "skipped":
        status, message = "not_configured", "n8n calendar webhook is not configured, no calendar event was created"
    else:
        status, message = "failed", f"Could not reach n8n to create the calendar event: {n8n_event.get('error', n8n_status)}"

    return {
        "status": status,
        "event_id": f"evt_{hash(client_name + property_title) % 10000}",
        "client_name": client_name,
        "property_title": property_title,
        "scheduled_at": event_time,
        "employee_email": employee_email,
        "meeting_link": "https://calendar.google.com/" if status == "queued_for_calendar" else None,
        "n8n_status": n8n_status,
        "message": message,
    }


def get_calendar_event(event_id: str) -> Dict[str, Any]:
    """Get details of a calendar event."""
    return {
        "status": "not_implemented",
        "message": "Calendar lookup requires n8n integration with Google Calendar API",
    }


def cancel_calendar_event(event_id: str) -> Dict[str, Any]:
    """Cancel a calendar event."""
    payload = {"event_id": event_id, "action": "cancel"}
    n8n_event = n8n_publisher.publish("calendar_event_cancelled", payload)

    return {
        "status": "queued_for_cancellation",
        "event_id": event_id,
        "n8n_status": n8n_event.get("status"),
    }

