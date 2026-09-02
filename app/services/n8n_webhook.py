"""
n8n Webhook Publisher

Publishes events to n8n webhooks for workflow automation.
n8n listens on these webhooks and triggers business processes:
- lead.created
- lead.updated
- appointment.scheduled
- followup.created
- session.completed
"""

import os
import json
import requests
from datetime import datetime
from typing import Dict, Any, Optional

from app.config import settings

# n8n webhook URLs (set via environment)
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678/webhook")
USE_MASTER_N8N_WORKFLOW = os.getenv("USE_MASTER_N8N_WORKFLOW", "true").lower() == "true"

# Master single webhook endpoint
N8N_MASTER_WEBHOOK = f"{N8N_BASE_URL}/real-estate-event"

# Event webhook endpoints (individual fallback endpoints)
N8N_WEBHOOKS = {
    "lead_created": f"{N8N_BASE_URL}/lead-created",
    "lead_updated": f"{N8N_BASE_URL}/lead-updated",
    "appointment_scheduled": f"{N8N_BASE_URL}/appointment-scheduled",
    "appointment_cancelled": f"{N8N_BASE_URL}/appointment-cancelled",
    "appointment_rescheduled": f"{N8N_BASE_URL}/appointment-rescheduled",
    "followup_created": f"{N8N_BASE_URL}/followup-created",
    "session_completed": f"{N8N_BASE_URL}/session-completed",
    "property_recommended": f"{N8N_BASE_URL}/property-recommended",
    "calendar_event_created": f"{N8N_BASE_URL}/calendar-event-created",
    "calendar_event_cancelled": f"{N8N_BASE_URL}/calendar-event-cancelled",
    "email_booking_sent": f"{N8N_BASE_URL}/email-booking-sent",
    "email_followup_sent": f"{N8N_BASE_URL}/email-followup-sent",
    "crm_contact_created": f"{N8N_BASE_URL}/crm-contact-created",
    "crm_contact_updated": f"{N8N_BASE_URL}/crm-contact-updated",
}


class N8NEventPublisher:
    """Publish events to n8n for workflow automation."""

    @staticmethod
    def publish(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publish an event to n8n webhook.
        
        Args:
            event_type: One of lead_created, lead_updated, appointment_scheduled, etc.
            payload: Event data to send
            
        Returns:
            Response from n8n (or error dict if webhook not configured)
        """
        webhook_url = N8N_MASTER_WEBHOOK if USE_MASTER_N8N_WORKFLOW else N8N_WEBHOOKS.get(event_type)
        if not webhook_url or not webhook_url.startswith("http"):
            return {
                "status": "skipped",
                "reason": f"n8n webhook for {event_type} not configured",
                "event_type": event_type,
                "payload_queued": True,
            }

        payload_with_meta = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload,
        }

        try:
            response = requests.post(
                webhook_url,
                json=payload_with_meta,
                timeout=5,
            )
            return {
                "status": "published",
                "event_type": event_type,
                "webhook_url": webhook_url,
                "response_code": response.status_code,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except requests.exceptions.Timeout:
            return {
                "status": "timeout",
                "event_type": event_type,
                "webhook_url": webhook_url,
                "error": "n8n webhook request timed out",
                "queued": True,
            }
        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "event_type": event_type,
                "webhook_url": webhook_url,
                "error": str(e),
                "queued": True,
            }

    @staticmethod
    def lead_created(lead_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Publish lead.created event."""
        payload = {
            "lead_id": lead_id,
            "profile": profile,
        }
        return N8NEventPublisher.publish("lead_created", payload)

    @staticmethod
    def lead_updated(lead_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Publish lead.updated event."""
        payload = {
            "lead_id": lead_id,
            "profile": profile,
        }
        return N8NEventPublisher.publish("lead_updated", payload)

    @staticmethod
    def appointment_scheduled(
        appointment_id: str,
        lead_id: str,
        property_name: str,
        client_name: str,
        scheduled_at: str,
    ) -> Dict[str, Any]:
        """Publish appointment.scheduled event."""
        payload = {
            "appointment_id": appointment_id,
            "lead_id": lead_id,
            "property_name": property_name,
            "client_name": client_name,
            "scheduled_at": scheduled_at,
        }
        return N8NEventPublisher.publish("appointment_scheduled", payload)

    @staticmethod
    def followup_created(
        followup_id: str,
        lead_id: str,
        note: str,
        scheduled_for: str,
    ) -> Dict[str, Any]:
        """Publish followup.created event."""
        payload = {
            "followup_id": followup_id,
            "lead_id": lead_id,
            "note": note,
            "scheduled_for": scheduled_for,
        }
        return N8NEventPublisher.publish("followup_created", payload)

    @staticmethod
    def session_completed(
        session_id: str,
        lead_id: str,
        transcript: str,
        intent: str,
        duration_seconds: int,
    ) -> Dict[str, Any]:
        """Publish session.completed event."""
        payload = {
            "session_id": session_id,
            "lead_id": lead_id,
            "transcript": transcript,
            "intent": intent,
            "duration_seconds": duration_seconds,
        }
        return N8NEventPublisher.publish("session_completed", payload)

    @staticmethod
    def property_recommended(
        session_id: str,
        property_id: str,
        property_name: str,
        city: str,
        area: str,
    ) -> Dict[str, Any]:
        """Publish property.recommended event."""
        payload = {
            "session_id": session_id,
            "property_id": property_id,
            "property_name": property_name,
            "city": city,
            "area": area,
        }
        return N8NEventPublisher.publish("property_recommended", payload)

    @staticmethod
    def appointment_cancelled(
        appointment_id: str,
        lead_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Publish appointment.cancelled event."""
        payload = {
            "appointment_id": appointment_id,
            "lead_id": lead_id,
            "reason": reason,
        }
        return N8NEventPublisher.publish("appointment_cancelled", payload)

    @staticmethod
    def appointment_rescheduled(
        appointment_id: str,
        lead_id: str,
        old_time: str,
        new_time: str,
    ) -> Dict[str, Any]:
        """Publish appointment.rescheduled event."""
        payload = {
            "appointment_id": appointment_id,
            "lead_id": lead_id,
            "old_time": old_time,
            "new_time": new_time,
        }
        return N8NEventPublisher.publish("appointment_rescheduled", payload)

    @staticmethod
    def calendar_event_created(
        event_id: str,
        title: str,
        start_time: str,
        attendee_email: str,
    ) -> Dict[str, Any]:
        """Publish calendar.event_created event."""
        payload = {
            "event_id": event_id,
            "title": title,
            "start_time": start_time,
            "attendee_email": attendee_email,
        }
        return N8NEventPublisher.publish("calendar_event_created", payload)

    @staticmethod
    def calendar_event_cancelled(event_id: str) -> Dict[str, Any]:
        """Publish calendar.event_cancelled event."""
        payload = {"event_id": event_id}
        return N8NEventPublisher.publish("calendar_event_cancelled", payload)

    @staticmethod
    def email_booking_sent(
        recipient: str,
        client_name: str,
        property_title: str,
    ) -> Dict[str, Any]:
        """Publish email.booking_sent event."""
        payload = {
            "recipient": recipient,
            "client_name": client_name,
            "property_title": property_title,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return N8NEventPublisher.publish("email_booking_sent", payload)

    @staticmethod
    def email_followup_sent(
        recipient: str,
        client_name: str,
    ) -> Dict[str, Any]:
        """Publish email.followup_sent event."""
        payload = {
            "recipient": recipient,
            "client_name": client_name,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return N8NEventPublisher.publish("email_followup_sent", payload)

    @staticmethod
    def crm_contact_created(lead_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Publish crm.contact_created event."""
        payload = {
            "lead_id": lead_id,
            "profile": profile,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return N8NEventPublisher.publish("crm_contact_created", payload)

    @staticmethod
    def crm_contact_updated(lead_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Publish crm.contact_updated event."""
        payload = {
            "lead_id": lead_id,
            "profile": profile,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return N8NEventPublisher.publish("crm_contact_updated", payload)


# Global instance
n8n_publisher = N8NEventPublisher()
