"""
Email Service

Sends booking confirmation and followup emails via SMTP.

Features:
- SMTP sends directly (Gmail App Password or any SMTP provider)
- HTML email body with appointment time, agent contact, and call summary
- Email header injection prevention (CR/LF stripped from all header fields)
- HTML body uses html.escape() on all user-supplied values
- Recipient allow-list enforced when ALLOWED_RECIPIENTS is set
- Call history summary included when the appointment was discussed on a prior call

Environment variables:
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
- DEFAULT_RECIPIENT_EMAIL
- ALLOWED_RECIPIENTS (comma-separated allow-list, optional but recommended)
- SENDER_NAME (display name for From: header)
"""

from __future__ import annotations

import html
import logging
import os
import re
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from app.services.n8n_webhook import n8n_publisher

load_dotenv()

logger = logging.getLogger("email_service")
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# SMTP configuration
# ---------------------------------------------------------------------------
_SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
_SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
_SMTP_USER = os.getenv("SMTP_USER", "")
_SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
_SMTP_FROM = os.getenv("SMTP_FROM", _SMTP_USER).rstrip("=")
_SENDER_NAME = os.getenv("SENDER_NAME", "Real Estate Hub Sales Team")
DEFAULT_RECIPIENT_EMAIL = os.getenv("DEFAULT_RECIPIENT_EMAIL", _SMTP_USER)

# Optional allow-list of recipient emails. If set, only these addresses
# will receive outbound email (greatly reduces the open-relay risk).
_ALLOWED_RECIPIENTS = {
    addr.strip().lower()
    for addr in os.getenv("ALLOWED_RECIPIENTS", "").split(",")
    if addr.strip()
}


# ---------------------------------------------------------------------------
# Input sanitization — header injection prevention
# ---------------------------------------------------------------------------
_HEADER_NEWLINE_RE = re.compile(r"[\r\n]")


def _sanitize_header(value: Optional[str], max_len: int = 200) -> str:
    """Strip CR/LF and limit length — used for any field placed in an
    email header (Subject, To, From, Reply-To, etc.)."""
    if not value:
        return ""
    cleaned = _HEADER_NEWLINE_RE.sub(" ", str(value)).strip()
    return cleaned[:max_len]


def _validate_email(addr: str) -> bool:
    """Basic RFC-822-ish email validation."""
    if not addr:
        return False
    return bool(re.match(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$", addr))


def _is_allowed_recipient(addr: str) -> bool:
    """If ALLOWED_RECIPIENTS is set, the recipient must be on the list."""
    if not _ALLOWED_RECIPIENTS:
        return True
    return addr.lower() in _ALLOWED_RECIPIENTS


# ---------------------------------------------------------------------------
# HTML body construction
# ---------------------------------------------------------------------------
def _format_when(scheduled_at: Optional[str]) -> str:
    """Pretty-print the appointment time for the email body."""
    if not scheduled_at:
        return "to be confirmed"
    try:
        dt = datetime.fromisoformat(scheduled_at)
        return dt.strftime("%A, %d %B %Y at %I:%M %p (UTC%z)")
    except (ValueError, TypeError):
        return _sanitize_header(scheduled_at) or "to be confirmed"


def _format_date_and_time(scheduled_at: Optional[str]) -> tuple[str, str]:
    """Split scheduled_at into separate date and time strings for the
    subject line and body fields. Falls back gracefully on bad input."""
    if not scheduled_at:
        return "to be confirmed", "to be confirmed"
    try:
        dt = datetime.fromisoformat(scheduled_at)
        return dt.strftime("%A, %d %B %Y"), dt.strftime("%I:%M %p")
    except (ValueError, TypeError):
        raw = _sanitize_header(scheduled_at) or "to be confirmed"
        return raw, raw


def _build_html_body(
    client_name: str,
    property_title: str,
    scheduled_at: Optional[str],
    employee_email: Optional[str],
    client_phone: Optional[str] = None,
    appointment_id: Optional[str] = None,
    call_history: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Build the HTML body for the booking confirmation email.

    All user-supplied values are html.escape()'d to prevent HTML injection.
    """
    safe_name = html.escape(client_name or "Customer")
    safe_title = html.escape(property_title or "the property")
    safe_phone = html.escape(client_phone or "your registered phone number")
    safe_ref = html.escape(appointment_id or "N/A")
    date_str, time_str = _format_date_and_time(scheduled_at)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Tahoma,Arial,sans-serif;">
  <div style="max-width:560px;margin:24px auto;background:#ffffff;border-radius:8px;padding:28px 32px;">
    <p style="font-size:15px;color:#111827;margin:0 0 16px;line-height:1.6;">
      Dear <strong>{safe_name}</strong>,
    </p>
    <p style="font-size:14px;color:#374151;line-height:1.6;margin:0 0 20px;">
      Your property visit is confirmed.
    </p>
    <table style="width:100%;border-collapse:collapse;margin:0 0 20px;font-size:14px;">
      <tr>
        <td style="padding:8px 0;color:#6b7280;width:35%;">Property</td>
        <td style="padding:8px 0;font-weight:600;color:#111827;">{safe_title}</td>
      </tr>
      <tr>
        <td style="padding:8px 0;color:#6b7280;border-top:1px solid #f3f4f6;">Date</td>
        <td style="padding:8px 0;font-weight:600;color:#111827;border-top:1px solid #f3f4f6;">{html.escape(date_str)}</td>
      </tr>
      <tr>
        <td style="padding:8px 0;color:#6b7280;border-top:1px solid #f3f4f6;">Time</td>
        <td style="padding:8px 0;font-weight:600;color:#111827;border-top:1px solid #f3f4f6;">{html.escape(time_str)}</td>
      </tr>
      <tr>
        <td style="padding:8px 0;color:#6b7280;border-top:1px solid #f3f4f6;">Booking reference</td>
        <td style="padding:8px 0;font-weight:600;color:#111827;border-top:1px solid #f3f4f6;">{safe_ref}</td>
      </tr>
    </table>
    <p style="font-size:14px;color:#374151;line-height:1.6;margin:0 0 20px;">
      Our agent will call you at <strong>{safe_phone}</strong> shortly before the visit
      to confirm the exact meeting point. If you need to reschedule or cancel, just
      reply to this email or call us back.
    </p>
    <p style="font-size:14px;color:#111827;margin:24px 0 0;">
      Best regards,<br>{html.escape(_SENDER_NAME)}
    </p>
  </div>
</body>
</html>"""


def _build_plain_body(
    client_name: str,
    property_title: str,
    scheduled_at: Optional[str],
    employee_email: Optional[str],
    client_phone: Optional[str],
    appointment_id: Optional[str] = None,
    call_history: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Plain-text body — also used as the HTML fallback content."""
    date_str, time_str = _format_date_and_time(scheduled_at)
    return f"""Dear {client_name or 'Customer'},

Your property visit is confirmed.

Property: {property_title or 'N/A'}
Date: {date_str}
Time: {time_str}
Booking reference: {appointment_id or 'N/A'}

Our agent will call you at {client_phone or 'your registered phone number'} shortly before the visit to confirm the exact meeting point. If you need to reschedule or cancel, just reply to this email or call us back.

Best regards,
{_SENDER_NAME}
"""


# ---------------------------------------------------------------------------
# SMTP send (always fires in parallel with n8n publishing)
# ---------------------------------------------------------------------------
def _send_smtp(
    to: str,
    subject: str,
    plain_body: str,
    html_body: Optional[str] = None,
) -> Dict[str, Any]:
    """Send email directly via SMTP. Returns a status dict."""
    # Resolve recipient
    to_address = to if (to and to != "not_provided") else DEFAULT_RECIPIENT_EMAIL
    if not to_address or not _validate_email(to_address):
        return {"status": "skipped", "reason": "invalid_recipient"}

    if not _is_allowed_recipient(to_address):
        logger.warning(f"[email] rejecting non-allow-listed recipient: {to_address}")
        return {"status": "skipped", "reason": "recipient_not_in_allow_list"}

    if not _SMTP_USER or not _SMTP_PASSWORD:
        return {"status": "skipped", "reason": "smtp_credentials_not_configured"}

    # Build MIME message — all header fields are sanitized
    safe_subject = _sanitize_header(subject)
    safe_to = _sanitize_header(to_address)
    safe_from = _sanitize_header(_SMTP_FROM)
    sender_display = _sanitize_header(_SENDER_NAME)

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = safe_subject
        msg["From"] = formataddr((sender_display, safe_from))
        msg["To"] = safe_to
        msg.attach(MIMEText(plain_body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        if _SMTP_PORT == 465:
            with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT, timeout=30) as server:
                server.ehlo()
                server.login(_SMTP_USER, _SMTP_PASSWORD)
                server.sendmail(safe_from, [safe_to], msg.as_string())
        else:
            with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(_SMTP_USER, _SMTP_PASSWORD)
                server.sendmail(safe_from, [safe_to], msg.as_string())

        logger.info(f"[email] SMTP sent -> {safe_to} | subject='{safe_subject[:60]}'")
        return {
            "status": "sent",
            "recipient": safe_to,
            "subject": safe_subject,
        }
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"[email] SMTP auth error: {e.smtp_code} {e.smtp_error!r}")
        return {
            "status": "error",
            "error": f"SMTP authentication failed (code {e.smtp_code})",
            "recipient": safe_to,
        }
    except Exception as e:
        logger.error(f"[email] SMTP error: {type(e).__name__}: {e}")
        return {
            "status": "error",
            "error": f"{type(e).__name__}: {str(e)[:200]}",
            "recipient": safe_to,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def send_booking_email(
    client_name: str,
    property_title: str,
    employee_email: Optional[str] = None,
    recipient_email: Optional[str] = None,
    scheduled_at: Optional[str] = None,
    client_phone: Optional[str] = None,
    appointment_id: Optional[str] = None,
    call_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Send booking confirmation email.

    Args:
        client_name: Name of the customer
        property_title: Property name being visited
        employee_email: Assigned agent's email (used as recipient if recipient_email is None)
        recipient_email: Override the recipient (must be on ALLOWED_RECIPIENTS if set)
        scheduled_at: ISO 8601 datetime of the confirmed visit
        client_phone: Phone number for the visit reminder
        appointment_id: Booking reference shown in the email
        call_history: Reserved for future use — not rendered in the current template

    Returns:
        Dict with send status. Never raises — callers can rely on a result.
    """
    # Resolve recipient
    if recipient_email and _validate_email(recipient_email):
        recipient = recipient_email
    elif employee_email and _validate_email(employee_email):
        recipient = employee_email
    else:
        recipient = DEFAULT_RECIPIENT_EMAIL or "not_provided"

    # Sanitize all header-bound values
    safe_name = _sanitize_header(client_name) or "Customer"
    safe_title = _sanitize_header(property_title) or "Property"
    date_str, _ = _format_date_and_time(scheduled_at)
    subject = f"Visit Confirmed - {safe_title}, {date_str}"

    plain_body = _build_plain_body(
        safe_name, safe_title, scheduled_at, employee_email, client_phone, appointment_id, call_history
    )
    html_body = _build_html_body(
        safe_name, safe_title, scheduled_at, employee_email, client_phone, appointment_id, call_history
    )

    # Publish to n8n in parallel (downstream automation only — does NOT gate SMTP)
    n8n_status = "skipped"
    try:
        n8n_event = n8n_publisher.publish("email_booking_sent", {
            "to": recipient,
            "subject": subject,
            "client_name": safe_name,
            "property_title": safe_title,
            "scheduled_at": scheduled_at,
            "client_phone": client_phone,
            "appointment_id": appointment_id,
            "agent_email": employee_email,
        })
        n8n_status = n8n_event.get("status", "unknown")
    except Exception as e:
        logger.warning(f"[email] n8n publish raised: {e}")

    # SMTP ALWAYS fires (actual delivery channel)
    smtp_result = _send_smtp(recipient, subject, plain_body, html_body=html_body)

    return {
        "status": smtp_result.get("status"),
        "recipient": smtp_result.get("recipient", recipient),
        "subject": smtp_result.get("subject", subject),
        "scheduled_at": scheduled_at,
        "n8n_status": n8n_status,
        "message": smtp_result.get("error") or "Email sent via SMTP (n8n published in parallel)",
    }


def send_followup_email(
    client_name: str,
    recipient_email: str,
    followup_message: str,
) -> Dict[str, Any]:
    """Send a follow-up email to a customer."""
    safe_name = _sanitize_header(client_name) or "Customer"
    safe_msg = html.escape(followup_message or "")[:4000]
    safe_addr = _sanitize_header(recipient_email)
    subject = "Follow-up from Real Estate Hub"

    plain_body = (
        f"Dear {safe_name},\n\n{followup_message}\n\n"
        "Best regards,\nReal Estate Hub Sales Team\n"
    )
    html_body = f"""<!DOCTYPE html>
<html><body style="font-family:Segoe UI,Arial,sans-serif;background:#f3f4f6;margin:0;padding:24px;">
  <div style="max-width:560px;margin:0 auto;background:#fff;border-radius:8px;padding:24px;">
    <p>Dear <strong>{safe_name}</strong>,</p>
    <p style="line-height:1.6;color:#374151;">{safe_msg}</p>
    <p style="color:#6b7280;font-size:13px;">Best regards,<br>Real Estate Hub Sales Team</p>
  </div>
</body></html>"""

    try:
        n8n_publisher.publish("email_followup_sent", {
            "to": safe_addr,
            "subject": subject,
            "client_name": safe_name,
        })
    except Exception as e:
        logger.warning(f"[email] n8n publish raised: {e}")

    smtp_result = _send_smtp(safe_addr, subject, plain_body, html_body=html_body)
    return {
        "status": smtp_result.get("status"),
        "recipient": smtp_result.get("recipient", safe_addr),
    }


def send_agent_notification(
    agent_email: str,
    subject: str,
    notification_type: str,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Send a notification email to an internal agent."""
    safe_addr = _sanitize_header(agent_email)
    safe_subject = _sanitize_header(subject)
    safe_type = html.escape(notification_type or "notification")
    # Render data dict safely
    data_lines = "\n".join(
        f"  - {html.escape(str(k))}: {html.escape(str(v))[:200]}"
        for k, v in (data or {}).items()
    )
    plain_body = (
        f"Hello,\n\nA new {notification_type} notification has been logged.\n\n"
        f"Details:\n{data_lines}\n\n— Real Estate Hub\n"
    )
    html_body = f"""<!DOCTYPE html>
<html><body style="font-family:Segoe UI,Arial,sans-serif;background:#f3f4f6;margin:0;padding:24px;">
  <div style="max-width:560px;margin:0 auto;background:#fff;border-radius:8px;padding:24px;">
    <p>Hello,</p>
    <p>A new <strong>{safe_type}</strong> notification has been logged.</p>
    <p style="line-height:1.6;color:#374151;"><pre style="white-space:pre-wrap;background:#f9fafb;padding:12px;border-radius:4px;font-size:13px;">{data_lines}</pre></p>
    <p style="color:#6b7280;font-size:13px;">— Real Estate Hub</p>
  </div>
</body></html>"""

    try:
        n8n_publisher.publish("email_agent_notification", {
            "to": safe_addr,
            "subject": safe_subject,
            "notification_type": notification_type,
            "data": data,
        })
    except Exception as e:
        logger.warning(f"[email] n8n publish raised: {e}")

    smtp_result = _send_smtp(safe_addr, safe_subject, plain_body, html_body=html_body)
    return {
        "status": smtp_result.get("status"),
        "recipient": smtp_result.get("recipient", safe_addr),
    }
