"""
Email Service

Tries to publish to n8n first. If n8n is unavailable, falls back to
sending email directly via SMTP using credentials from the environment.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any

from app.services.n8n_webhook import n8n_publisher

from dotenv import load_dotenv

load_dotenv()

# SMTP settings from .env
_SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
_SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
_SMTP_USER = os.getenv("SMTP_USER", "")
_SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
_SMTP_FROM = os.getenv("SMTP_FROM", _SMTP_USER).rstrip("=")  # strip accidental trailing =


# Default recipient for testing / fallback
DEFAULT_RECIPIENT_EMAIL = os.getenv("DEFAULT_RECIPIENT_EMAIL", _SMTP_USER)


def _send_smtp(to: str, subject: str, body: str) -> Dict[str, Any]:
    """Send email directly via SMTP (Gmail or any SMTP provider)."""
    to_address = to if (to and to != "not_provided") else DEFAULT_RECIPIENT_EMAIL
    if not _SMTP_USER or not _SMTP_PASSWORD:
        return {"status": "skipped", "reason": "SMTP credentials not configured"}
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = _SMTP_FROM
        msg["To"] = to_address
        msg.attach(MIMEText(body, "plain"))

        if _SMTP_PORT == 465:
            with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT) as server:
                server.login(_SMTP_USER, _SMTP_PASSWORD)
                server.sendmail(_SMTP_FROM, [to_address], msg.as_string())
        else:
            with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.login(_SMTP_USER, _SMTP_PASSWORD)
                server.sendmail(_SMTP_FROM, [to_address], msg.as_string())

        return {"status": "sent", "recipient": to_address, "subject": subject}
    except Exception as e:
        return {"status": "error", "error": str(e), "recipient": to_address}


def send_booking_email(
    client_name: str,
    property_title: str,
    employee_email: str | None = None,
    recipient_email: str | None = None,
) -> Dict[str, Any]:
    """
    Send booking confirmation email.

    Tries n8n first. Falls back to direct SMTP if n8n is unavailable.
    """
    recipient = recipient_email or employee_email or DEFAULT_RECIPIENT_EMAIL or "not_provided"
    subject = f"Property Visit Booking Confirmation - {property_title}"
    body = f"""Dear {client_name},

Thank you for your interest in {property_title}.

Your property visit has been scheduled. Our team will contact you shortly to confirm the exact time.

Best regards,
Real Estate Hub Sales Team
"""

    # Try n8n first
    email_payload = {
        "to": recipient,
        "subject": subject,
        "body": body,
        "client_name": client_name,
        "property_title": property_title,
        "agent_email": employee_email,
    }
    n8n_event = n8n_publisher.publish("email_booking_sent", email_payload)
    n8n_status = n8n_event.get("status")

    if n8n_status == "published":
        return {
            "status": "queued_for_email",
            "recipient": recipient,
            "client_name": client_name,
            "property_title": property_title,
            "subject": subject,
            "n8n_status": n8n_status,
            "message": "Email queued for n8n delivery",
        }

    # n8n unavailable — fall back to direct SMTP
    smtp_result = _send_smtp(recipient, subject, body)
    return {
        "status": smtp_result.get("status"),
        "recipient": recipient,
        "client_name": client_name,
        "property_title": property_title,
        "subject": subject,
        "n8n_status": n8n_status,
        "message": smtp_result.get("error") or "Email sent directly via SMTP (n8n not available)",
    }


def send_followup_email(
    client_name: str,
    recipient_email: str,
    followup_message: str,
) -> Dict[str, Any]:
    """Send a followup email to a client."""
    payload = {
        "to": recipient_email,
        "subject": "Follow-up from Real Estate Hub",
        "client_name": client_name,
        "message": followup_message,
    }
    n8n_event = n8n_publisher.publish("email_followup_sent", payload)
    n8n_status = n8n_event.get("status")

    return {
        "status": "queued_for_email" if n8n_status == "published" else ("not_configured" if n8n_status == "skipped" else "failed"),
        "recipient": recipient_email,
        "n8n_status": n8n_status,
    }


def send_agent_notification(
    agent_email: str,
    subject: str,
    notification_type: str,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Send a notification email to an agent."""
    payload = {
        "to": agent_email,
        "subject": subject,
        "notification_type": notification_type,
        "data": data,
    }
    n8n_event = n8n_publisher.publish("email_agent_notification", payload)
    n8n_status = n8n_event.get("status")

    return {
        "status": "queued_for_email" if n8n_status == "published" else ("not_configured" if n8n_status == "skipped" else "failed"),
        "recipient": agent_email,
        "n8n_status": n8n_status,
    }

