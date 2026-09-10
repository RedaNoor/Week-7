"""
SMTP Integration Test Script
============================

Tests the email SMTP integration that fires on appointment confirmation.
Sends real test emails using credentials from the .env file, and diagnoses
common reasons a confirmation email might never reach the inbox:

1. SMTP credentials present / formatted correctly?
2. SSL (port 465) vs STARTTLS (port 587) handshake works?
3. Recipient resolution path (employee_email -> DEFAULT_RECIPIENT_EMAIL).
4. n8n webhook taking precedence over SMTP fallback (the actual reason
   most appointments "don't send" an email — the system queues to n8n
   and never falls through to SMTP).
5. End-to-end test simulating the POST /appointments flow.
"""

import os
import sys
import smtplib
import time
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Make sure we load .env from the backend dir
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER).rstrip("=")
DEFAULT_RECIPIENT = os.getenv("DEFAULT_RECIPIENT_EMAIL", SMTP_USER)
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "")

print("=" * 70)
print("SMTP INTEGRATION DIAGNOSTIC")
print("=" * 70)
print(f"Host            : {SMTP_HOST}")
print(f"Port            : {SMTP_PORT}")
print(f"User            : {SMTP_USER}")
print(f"Password (len)  : {len(SMTP_PASSWORD)} chars")
print(f"From            : {SMTP_FROM}")
print(f"Default To      : {DEFAULT_RECIPIENT}")
print(f"n8n base URL    : {N8N_BASE_URL or '(not set)'}")
print()


# --- Step 1: validate credentials ---
print("[1/5] Validating SMTP credentials...")
issues = []
if not SMTP_USER:
    issues.append("SMTP_USER is empty")
if not SMTP_PASSWORD:
    issues.append("SMTP_PASSWORD is empty")
if " " not in SMTP_PASSWORD and SMTP_PASSWORD and len(SMTP_PASSWORD) < 16:
    issues.append("SMTP_PASSWORD looks like a regular Gmail password, not an App Password "
                  "(App Passwords are 16 chars and contain spaces like 'abcd efgh ijkl mnop')")
if SMTP_PASSWORD and " " in SMTP_PASSWORD:
    print(f"     -> App Password detected (looks valid, {len(SMTP_PASSWORD.split())} groups)")
if issues:
    for i in issues:
        print(f"     ! {i}")
else:
    print("     -> Credentials look structurally valid.")
print()


# --- Step 2: TCP connectivity ---
print("[2/5] Testing TCP connectivity to SMTP server...")
import socket
try:
    sock = socket.create_connection((SMTP_HOST, SMTP_PORT), timeout=10)
    sock.close()
    print(f"     -> TCP connect to {SMTP_HOST}:{SMTP_PORT} succeeded.")
except Exception as e:
    print(f"     ! TCP connect failed: {e}")
print()


# --- Step 3: SMTP login + send test email ---
print("[3/5] Sending a real test email via SMTP...")
test_recipient = DEFAULT_RECIPIENT
test_subject = f"[SMTP TEST] Real Estate Agent - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
test_body = f"""Hello,

This is a diagnostic test email from the Real Estate Voice Agent backend.

If you are reading this, your SMTP integration is working correctly.

Test details:
- Host: {SMTP_HOST}
- Port: {SMTP_PORT}
- User: {SMTP_USER}
- Sent at: {datetime.now().isoformat()}
- Method: {"SMTP_SSL" if SMTP_PORT == 465 else "STARTTLS"}

— Real Estate AI Agent
"""

send_result = None
try:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = test_subject
    msg["From"] = SMTP_FROM
    msg["To"] = test_recipient
    msg.attach(MIMEText(test_body, "plain"))

    if SMTP_PORT == 465:
        print(f"     -> Using SMTP_SSL on port 465...")
        with smtplib.SMTP_SSL(SSMTP_HOST := SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [test_recipient], msg.as_string())
    else:
        print(f"     -> Using STARTTLS on port {SMTP_PORT}...")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [test_recipient], msg.as_string())

    send_result = {"status": "sent", "recipient": test_recipient, "subject": test_subject}
    print(f"     -> Email accepted by SMTP server, queued for delivery to {test_recipient}")
except Exception as e:
    send_result = {"status": "error", "error": str(e), "recipient": test_recipient}
    print(f"     ! SMTP send failed: {type(e).__name__}: {e}")
print()


# --- Step 4: Test the actual email_service.send_booking_email path ---
print("[4/5] Calling app.services.email_service.send_booking_email() (production code path)...")
try:
    from app.services.email_service import send_booking_email
    # IMPORTANT: simulate what POST /appointments does
    prod_result = send_booking_email(
        client_name="Test Client",
        property_title="Green Valley Residency (P001)",
        employee_email=None,        # this is what triggers the bug — see diagnosis below
        recipient_email=None,
    )
    print(f"     -> Production call result:")
    print(f"        {json.dumps(prod_result, indent=2, default=str)}")
    print()
    print("     DIAGNOSIS:")
    if prod_result.get("status") == "queued_for_email":
        print("     ! EMAIL WAS QUEUED TO n8n, NOT SENT VIA SMTP.")
        print(f"       n8n webhook: {N8N_BASE_URL}/real-estate-event")
        print("       Since n8n is not running in this environment, the email will NEVER be sent.")
        print("       This is almost certainly why you never received the confirmation email.")
    elif prod_result.get("status") == "sent":
        print("     OK: SMTP fallback fired and email was sent.")
    elif prod_result.get("status") == "error":
        print(f"     ! SMTP send returned an error: {prod_result.get('message')}")
    elif prod_result.get("status") == "skipped":
        print("     ! SMTP send was skipped (credentials not configured).")
except Exception as e:
    print(f"     ! Production call raised: {type(e).__name__}: {e}")
print()


# --- Step 5: Simulate the full POST /appointments flow ---
print("[5/5] Simulating POST /appointments end-to-end (no n8n in path)...")
try:
    from app.services.appointment_service import create_appointment_record
    from app.services.email_service import send_booking_email
    from app.services.calendar_service import create_calendar_event

    # Use a future ISO datetime
    future_dt = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0).isoformat()

    appointment = create_appointment_record({
        "client_name": "SMTP Test Client",
        "client_phone": "+923001234567",
        "property_id": "P001",
        "property_title": "Green Valley Residency",
        "scheduled_at": future_dt,
        "employee_email": None,
    })
    print(f"     -> Appointment created: {appointment['appointment_id']}")

    email = send_booking_email(
        client_name=appointment["client_name"],
        property_title=appointment["property_title"],
        employee_email=appointment.get("employee_email"),
    )
    print(f"     -> Email result: {json.dumps(email, indent=2, default=str)}")
    print()
    print("     FINAL DIAGNOSIS:")
    if email.get("status") == "queued_for_email":
        print("     ❌ Email was routed to n8n (which is unavailable). Recipient will never see it.")
        print("        FIX: In email_service.send_booking_email(), don't return early when")
        print("        n8n publishes — also send via SMTP as a parallel/confirm path, OR")
        print("        detect n8n down and fall through to SMTP.")
    elif email.get("status") == "sent":
        print("     ✅ Email sent via SMTP. Check your inbox / spam folder for the test email.")
    elif email.get("status") == "error":
        print(f"     ❌ SMTP send error: {email.get('message')}")
except Exception as e:
    print(f"     ! End-to-end simulation failed: {type(e).__name__}: {e}")
print()


print("=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)
print()
print("Summary of likely root cause:")
print("  The original code calls n8n_publisher.publish() first, and if n8n returns")
print("  'published' (or any non-error status), it returns 'queued_for_email' WITHOUT")
print("  sending via SMTP. Since your n8n instance is not running, no email ever leaves.")
print("  Even when n8n is down, requests.exceptions.RequestException returns status='error'")
print("  but the code still treats the queued flag as authoritative.")
print()
print("Fix being applied in next step: patch email_service.py to ALWAYS also send via SMTP")
print("(SMTP is the source of truth for delivery), while still publishing the n8n event.")
