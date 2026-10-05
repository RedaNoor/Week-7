"""
Real Estate Voice Agent — FastAPI application entry point.

Provides REST endpoints for:
- Property catalog browsing
- Lead analysis and session state
- Appointment booking (with confirmation email + call history)
- Conversational agent (LangGraph orchestrator + ML memory)
- Telephony webhooks (Twilio / Vapi / Deepgram)
- n8n orchestration endpoints (lead sync, followups, webhook confirmations)

Security:
- CORS allow-list (configurable via TRUSTED_ORIGINS)
- API key authentication on sensitive endpoints (X-API-Key header)
- Rate limiting per IP (in-memory, sliding window)
- Input validation with strict Pydantic models
- Audit logging with PII redaction
- Email header / HTML injection prevention
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, EmailStr, Field, ConfigDict
try:
    from twilio.twiml.voice_response import VoiceResponse
    _TWILIO_AVAILABLE = True
except ImportError:
    VoiceResponse = None  # type: ignore
    _TWILIO_AVAILABLE = False

from .config import settings
from .services.appointment_service import (
    cancel_appointment_record,
    create_appointment_record,
    get_appointment,
    list_appointments,
    reschedule_appointment_record,
)
from .services.call_intent import detect_intent
from .services.call_history import call_history_store
from .services.calendar_service import create_calendar_event
from .services.conversation_learning import learner as conversation_learner
from .services.crm_service import log_call_and_booking, create_crm_contact
from .services.db_store import init_db, save_lead_profile, fetch_lead
from .services.db_store_enhanced import init_db as init_enhanced_db
from .services.email_service import send_booking_email, send_followup_email
try:
    from .services.langgraph_agent import orchestrator, strip_unwanted_greetings
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    orchestrator = None  # type: ignore
    strip_unwanted_greetings = None  # type: ignore
    _LANGCHAIN_AVAILABLE = False
from .services.chat_agent_fallback import process_chat_turn, strip_unwanted_greetings as fallback_strip_greetings
from .services.lead_memory import lead_memory
from .services.n8n_webhook import n8n_publisher
from .services.property_matcher import PROPERTY_CATALOG, match_properties
from .services.security import (
    AuditLogMiddleware,
    rate_limit,
    rate_limiter,
    redact_pii,
    require_admin_key,
    require_api_key,
    sanitize_header,
    sanitize_property_id,
    sanitize_session_id,
    sanitize_text,
    get_trusted_origins,
    now_iso,
)
from .services.session_state import session_state
from .orchestrator_endpoints import router as orchestrator_router
from .ml_endpoints import router as ml_router
from .services.auth_service import (
    register_user,
    authenticate_user,
    get_current_user,
    get_current_user_optional,
    require_admin_user,
)
try:
    from .services.vapi_service import handle_vapi_webhook, get_vapi_config
    _VAPI_AVAILABLE = True
except ImportError:
    handle_vapi_webhook = None  # type: ignore
    get_vapi_config = None  # type: ignore
    _VAPI_AVAILABLE = False

# Detect serverless / Vercel environment
SERVERLESS_MODE = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")
logger.info(f"Starting {settings.app_name} (env={settings.app_env})")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Real Estate Voice Agent",
    description="REST API for property leads, appointments, and the conversational agent.",
    version="1.0.0",
)

# Initialize databases (best-effort — server still boots if DB is down)
try:
    init_db()
    init_enhanced_db()
except Exception as e:
    logger.error(f"Database initialization warning: {e}")

# Include orchestrator endpoints (n8n integration)
app.include_router(orchestrator_router)
app.include_router(ml_router)

# CORS — explicit allow-list, NOT "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_trusted_origins(),
    allow_credentials=False,  # we use API keys, not cookies — no credentials needed
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
    max_age=600,
)

# Audit logging middleware — must be added last so it wraps everything
app.add_middleware(AuditLogMiddleware)


# ===========================================================================
# Request models (strict validation)
# ===========================================================================
class AppointmentRequest(BaseModel):
    """Request body for POST /appointments."""
    model_config = ConfigDict(extra="forbid")

    client_name: str = Field(..., min_length=1, max_length=120)
    client_phone: str = Field(..., min_length=4, max_length=30,
                              pattern=r"^\+?[0-9\s\-]{4,30}$")
    property_id: Optional[str] = Field(default="", min_length=2, max_length=20)
    property_title: str = Field(..., min_length=1, max_length=200)
    scheduled_at: str = Field(..., min_length=10, max_length=40)
    employee_email: Optional[EmailStr] = None
    recipient_email: Optional[EmailStr] = None
    lead_id: Optional[str] = Field(None, max_length=80)
    session_id: Optional[str] = Field(None, max_length=80)


class RescheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_time: str = Field(..., min_length=10, max_length=40)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(..., min_length=1, max_length=80)
    message: str = Field(..., min_length=1, max_length=8000)
    lead_id: Optional[str] = Field(None, max_length=80)
    customer_name: Optional[str] = Field(None, max_length=120)
    customer_email: Optional[str] = Field(None, max_length=120)
    customer_phone: Optional[str] = Field(None, max_length=40)


class LearnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(..., min_length=1, max_length=80)
    user_query: str = Field(..., min_length=1, max_length=8000)
    assistant_response: str = Field(..., min_length=1, max_length=8000)
    intent: str = Field("unknown", max_length=60)
    outcome: Optional[str] = Field(None, max_length=40)
    profile: Optional[Dict[str, Any]] = Field(None)


class CallHistoryRecordRequest(BaseModel):
    """Request body for POST /call-history — record a call where time was discussed."""
    model_config = ConfigDict(extra="forbid")
    lead_id: str = Field(..., min_length=1, max_length=80)
    client_phone: Optional[str] = Field(None, max_length=30)
    client_name: Optional[str] = Field(None, max_length=120)
    property_id: Optional[str] = Field(None, max_length=20)
    property_title: Optional[str] = Field(None, max_length=200)
    discussed_time: Optional[str] = Field(None, max_length=80)
    call_summary: Optional[str] = Field(None, max_length=500)
    transcript: Optional[str] = Field(None, max_length=10000)


class SessionTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(..., min_length=1, max_length=80)
    transcript: str = Field(..., min_length=1, max_length=8000)


class OrchestratorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(..., min_length=1, max_length=80)
    transcript: str = Field(..., min_length=1, max_length=8000)
    lead_id: Optional[str] = Field(None, max_length=80)


class FollowupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lead_id: str = Field(..., min_length=1, max_length=80)
    note: str = Field(..., min_length=1, max_length=2000)
    scheduled_for: str = Field(..., min_length=10, max_length=40)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(..., min_length=4, max_length=100)
    name: str = Field("Valued Client", min_length=1, max_length=120)
    role: Optional[str] = Field("user", max_length=20)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=100)


# ===========================================================================
# Authentication & User Management Endpoints
# ===========================================================================
@app.post("/auth/register", dependencies=[Depends(rate_limit("default"))])
def auth_register(payload: RegisterRequest):
    """Register a new user account."""
    try:
        res = register_user(
            email=str(payload.email),
            password=payload.password,
            name=payload.name,
            role=payload.role or "user"
        )
        return res
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/auth/login", dependencies=[Depends(rate_limit("default"))])
def auth_login(payload: LoginRequest):
    """Authenticate existing user or admin."""
    try:
        res = authenticate_user(
            email=str(payload.email),
            password=payload.password
        )
        return res
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/auth/me")
def auth_get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return currently logged in user profile."""
    return {"user": current_user}


# ===========================================================================
# Vapi Voice Call & Webhook Endpoints
# ===========================================================================
@app.get("/agent/vapi-config")
def get_vapi_config_endpoint():
    """Returns public Vapi credentials and agent configuration for Web Calls."""
    if not _VAPI_AVAILABLE or get_vapi_config is None:
        return {"status": "unavailable", "detail": "Vapi service not available in this deployment"}
    return get_vapi_config()


@app.post("/api/vapi/call", dependencies=[Depends(get_current_user)])
def vapi_call_endpoint(payload: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Trigger a Vapi call for the given lead.
    Expected payload: {"lead_id": "..."}
    For now this simply forwards the request to the Vapi webhook URL using the stored API key.
    """
    lead_id = payload.get("lead_id")
    if not lead_id:
        raise HTTPException(status_code=400, detail="lead_id required")
    # Construct a minimal Vapi call payload (placeholder)
    vapi_payload = {"lead_id": lead_id, "user_id": current_user["id"]}
    # In a real implementation you'd call Vapi's API here.
    # For now just log and return success.
    logger.info(f"Vapi call triggered for lead {lead_id} by user {current_user['email']}")
    return {"status": "queued", "lead_id": lead_id}


@app.post("/webhooks/vapi")
async def vapi_webhook_endpoint(request: Request):
    """Incoming webhook from Vapi AI Voice platform."""
    try:
        payload = await request.json()
        result = handle_vapi_webhook(payload)
        return result
    except Exception as exc:
        logger.error(f"Error handling Vapi webhook: {exc}")
        return {"status": "error", "detail": str(exc)}


# ===========================================================================
# Public endpoints (read-only, low-sensitivity)
# ===========================================================================
@app.get("/")
def healthcheck():
    """Unauthenticated health check — returns minimal info."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "1.0.0",
        "time": now_iso(),
    }


@app.get("/health", include_in_schema=True)
def health():
    """Standard health endpoint for container and orchestrator probes."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "1.0.0",
        "time": now_iso(),
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Silence browser /favicon.ico 404 logs."""
    return Response(status_code=204)


@app.get("/dashboard")
async def serve_dashboard():
    """Serve the minimalist dashboard HTML (no embedded data, safe to expose)."""
    dashboard_path = Path(__file__).resolve().parent.parent / "dashboard.html"
    if dashboard_path.exists():
        return FileResponse(dashboard_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Dashboard file not found")


# ===========================================================================
# Property catalog (read-only, public)
# ===========================================================================
@app.get("/properties",
         dependencies=[Depends(rate_limit("default"))])
def list_properties(
    city: Optional[str] = None,
    property_type: Optional[str] = None,
    limit: int = 100,
):
    """List properties, optionally filtered by city / type."""
    # Clamp limit to prevent exfiltration
    limit = max(1, min(limit, 200))
    items = PROPERTY_CATALOG
    if city:
        items = [p for p in items if p.get("city", "").lower() == city.lower()]
    if property_type:
        items = [p for p in items if p.get("type", "").lower() == property_type.lower()]
    return {"properties": items[:limit], "total": len(items)}


@app.get("/properties/{property_id}",
         dependencies=[Depends(rate_limit("default"))])
def get_property(property_id: str):
    """Get a single property's details + brochure.

    Property ID is validated against ^[Pp]\\d{3}$ and the canonical
    catalog value is used for the file path lookup (prevents path traversal).
    """
    canonical_id = sanitize_property_id(property_id)
    if not canonical_id:
        raise HTTPException(status_code=400, detail="Invalid property ID format")

    for p in PROPERTY_CATALOG:
        if str(p.get("property_id")).upper() == canonical_id:
            brochure = ""
            brochure_path = (
                Path(__file__).resolve().parent.parent
                / "documents" / "property_brochures"
                / f"{canonical_id}.txt"
            )
            # Defense-in-depth: ensure resolved path is inside the brochures dir
            brochures_dir = (
                Path(__file__).resolve().parent.parent
                / "documents" / "property_brochures"
            ).resolve()
            try:
                resolved = brochure_path.resolve()
                if not str(resolved).startswith(str(brochures_dir)):
                    raise HTTPException(status_code=400, detail="Invalid property ID")
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid property ID")
            if brochure_path.exists():
                try:
                    brochure = brochure_path.read_text(encoding="utf-8")[:20000]
                except Exception:
                    brochure = ""
            return {**p, "brochure": brochure}
    raise HTTPException(status_code=404, detail=f"Property {canonical_id} not found")


# ===========================================================================
# Leads & appointments
# ===========================================================================
@app.get("/leads",
         dependencies=[Depends(get_current_user), Depends(rate_limit("default"))])
def get_leads():
    """Return captured leads (authenticated — exposes PII)."""
    leads: List[Dict[str, Any]] = []
    if hasattr(lead_memory, "leads") and lead_memory.leads:
        for call_id, data in lead_memory.leads.items():
            profile = data.get("profile", {}) or {}
            location = ", ".join(
                part for part in [profile.get("area"), profile.get("city")] if part
            ) or "N/A"
            leads.append({
                "id": call_id,
                "name": profile.get("customer_name") or "Unknown",
                "budget": profile.get("budget") or "N/A",
                "location": location,
                "property_type": profile.get("property_type") or "N/A",
                "intent": data.get("intent", "unknown"),
                "transcript": (data.get("transcript", "") or "")[:100],
            })

    db_lead = fetch_lead("lead_analyze")
    if db_lead:
        leads.append({
            "id": "lead_analyze",
            "name": db_lead.get("customer_name") or "DB Lead",
            "budget": db_lead.get("profile", {}).get("budget", "N/A"),
            "location": db_lead.get("profile", {}).get("area", "N/A"),
            "property_type": db_lead.get("profile", {}).get("property_type", "N/A"),
            "intent": "persisted",
            "transcript": "database-backed lead profile",
        })
    return {"leads": leads}


@app.get("/appointments",
         dependencies=[Depends(rate_limit("default"))])
def get_appointments(current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Return appointments. Regular users see only their appointments; Super Admin sees all."""
    try:
        if not current_user:
            # Unauthenticated visitors cannot see any booked appointments
            return {"appointments": []}

        owner_email = None
        if current_user.get("role") != "admin":
            owner_email = current_user.get("email")

        appointments = []
        for apt in list_appointments(owner_email=owner_email):
            apt_id = apt.get("appointment_id") or apt.get("id") or ""
            appointments.append({
                "id": apt_id,
                "appointment_id": apt_id,
                "client_name": apt.get("client_name", "Unknown"),
                "client_phone": apt.get("client_phone", "N/A"),
                "property_id": apt.get("property_id", ""),
                "property_title": apt.get("property_title", "N/A"),
                "scheduled_at": apt.get("scheduled_at", "TBA"),
                "status": apt.get("status", "confirmed"),
                "employee_email": apt.get("employee_email") or apt.get("client_email"),
                "client_email": apt.get("client_email") or apt.get("employee_email"),
            })
        return {"appointments": appointments}
    except Exception as e:
        logger.exception(f"Error fetching appointments: {e}")
        return {"appointments": []}


@app.get("/appointments/{appointment_id}",
         dependencies=[Depends(require_api_key), Depends(rate_limit("default"))])
def get_appointment_endpoint(appointment_id: str):
    """Get a single appointment by ID."""
    apt = get_appointment(appointment_id)
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return apt


@app.post("/appointments",
          dependencies=[Depends(require_api_key), Depends(rate_limit("appointments"))])
def create_appointment(
    payload: AppointmentRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """Book a property visit.

    Triggers:
    - Appointment record creation (UUID-based, persisted to Postgres)
    - Calendar event (via n8n or local)
    - Booking confirmation email via SMTP (includes call-history summary)
    - CRM log entry
    - Call history record linking the booking to prior calls
    """
    try:
        user_email = current_user.get("email") if current_user else None
        # Build the dict with sanitized values
        apt_payload = {
            "client_name": sanitize_text(payload.client_name, 120),
            "client_phone": sanitize_text(payload.client_phone, 30),
            "property_id": sanitize_property_id(payload.property_id) or payload.property_id,
            "property_title": sanitize_text(payload.property_title, 200),
            "scheduled_at": sanitize_text(payload.scheduled_at, 40),
            "employee_email": str(payload.employee_email) if payload.employee_email else user_email,
            "recipient_email": str(payload.recipient_email) if payload.recipient_email else (str(payload.employee_email) if payload.employee_email else user_email),
            "lead_id": sanitize_session_id(payload.lead_id) if payload.lead_id else None,
            "session_id": sanitize_session_id(payload.session_id) if payload.session_id else None,
        }
        appointment = create_appointment_record(apt_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Pull call history for this lead / phone — to include in the email body
    lead_id = apt_payload.get("lead_id") or apt_payload.get("client_phone")
    call_history: List[Dict[str, Any]] = []
    if lead_id:
        try:
            raw_history = call_history_store.get_history_for_lead(str(lead_id))
            # Format for the email body
            for call in raw_history:
                call_history.append({
                    "call_time": (
                        datetime.fromisoformat(call["call_time"]).strftime(
                            "%d %b %Y, %I:%M %p"
                        ) if call.get("call_time") else ""
                    ),
                    "discussed_time": call.get("discussed_time") or "",
                    "summary": call.get("call_summary") or "",
                })
        except Exception as e:
            logger.warning(f"Could not load call history for lead {lead_id}: {e}")

    calendar = create_calendar_event(
        client_name=appointment["client_name"],
        property_title=appointment["property_title"],
        scheduled_at=appointment["scheduled_at"],
        employee_email=appointment.get("employee_email"),
    )
    email = send_booking_email(
        client_name=appointment["client_name"],
        property_title=appointment["property_title"],
        employee_email=appointment.get("employee_email"),
        recipient_email=appointment.get("recipient_email"),
        scheduled_at=appointment["scheduled_at"],
        client_phone=appointment.get("client_phone"),
        appointment_id=appointment.get("appointment_id"),
        call_history=call_history,
    )
    crm = log_call_and_booking(
        client_name=appointment["client_name"],
        phone=appointment["client_phone"],
        property_title=appointment["property_title"],
        status=appointment["status"],
    )
    return {
        "status": "created",
        "appointment_id": appointment.get("appointment_id"),
        "appointment": appointment,
        "calendar": calendar,
        "email": email,
        "crm": crm,
    }


@app.put("/appointments/{appointment_id}",
         dependencies=[Depends(require_api_key), Depends(rate_limit("appointments"))])
def reschedule_appointment(appointment_id: str, payload: RescheduleRequest):
    try:
        appointment = reschedule_appointment_record(appointment_id, payload.new_time)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "updated", "appointment_id": appointment_id, "appointment": appointment}


@app.delete("/appointments/{appointment_id}",
            dependencies=[Depends(require_api_key), Depends(rate_limit("appointments"))])
def cancel_appointment(appointment_id: str):
    try:
        appointment = cancel_appointment_record(appointment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "cancelled", "appointment_id": appointment_id, "appointment": appointment}


# ===========================================================================
# Call history (records times discussed on calls — surfaces in confirmation emails)
# ===========================================================================
@app.post("/call-history",
          dependencies=[Depends(get_current_user), Depends(rate_limit("default"))])
def record_call_history(payload: CallHistoryRecordRequest):
    """Record a call where an appointment time was discussed.

    The most recent discussed_time for a lead will be included in the
    booking confirmation email body when /appointments is called.
    """
    lead_id = sanitize_session_id(payload.lead_id)
    record = call_history_store.record_call(
        lead_id=lead_id,
        client_phone=sanitize_text(payload.client_phone, 30) if payload.client_phone else None,
        client_name=sanitize_text(payload.client_name, 120) if payload.client_name else None,
        property_id=sanitize_property_id(payload.property_id) if payload.property_id else None,
        property_title=sanitize_text(payload.property_title, 200) if payload.property_title else None,
        discussed_time=sanitize_text(payload.discussed_time, 80) if payload.discussed_time else None,
        call_summary=sanitize_text(payload.call_summary, 500) if payload.call_summary else None,
        transcript=sanitize_text(payload.transcript, 10000) if payload.transcript else None,
    )
    return {"status": "recorded", "record": record}


@app.get("/call-history/{lead_id}",
         dependencies=[Depends(get_current_user), Depends(rate_limit("default"))])
def get_call_history(lead_id: str, limit: int = 10):
    """Return call history for a lead (authenticated — exposes PII)."""
    lead_id = sanitize_session_id(lead_id)
    limit = max(1, min(limit, 50))
    history = call_history_store.get_history_for_lead(lead_id, limit)
    return {"lead_id": lead_id, "history": history, "count": len(history)}


# ===========================================================================
# Telephony webhooks (Twilio / Vapi / Deepgram)
# NOTE: Production deployments MUST verify webhook signatures.
# ===========================================================================
@app.post("/twilio/voice")
async def twilio_voice(request: Request):
    """Inbound Twilio voice webhook."""
    if not _TWILIO_AVAILABLE:
        raise HTTPException(status_code=503, detail="Twilio not available in this deployment")
    body = await request.body()
    from app.services.security import verify_twilio_signature
    if not verify_twilio_signature(request, body):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    form = await request.form()
    caller = (form.get("From") or "unknown caller")[:20]

    response = VoiceResponse()
    response.say(
        "Assalam-o-Alaikum. Welcome to Real Estate Hub. I am your virtual sales assistant. "
        "Please hold while I understand your requirements.",
        voice="Polly.Aditi",
        language="en-IN",
    )
    response.pause(length=1)
    response.say(f"Caller {caller} has reached the real estate assistant.", voice="Polly.Aditi")
    return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/twilio/status")
async def twilio_status(request: Request):
    body = await request.body()
    from app.services.security import verify_twilio_signature
    if not verify_twilio_signature(request, body):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
    payload = await request.form()
    return JSONResponse({"status": "ok", "call_status": payload.get("CallStatus", "unknown")})


@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    """Inbound Vapi webhook. Production should verify HMAC signature."""
    payload = await request.json()
    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
    call = payload.get("call") if isinstance(payload.get("call"), dict) else {}
    call_id = payload.get("call_id") or payload.get("id") or call.get("id") or "unknown"
    transcript = payload.get("transcript") or message.get("transcript") or ""
    if not transcript and isinstance(message.get("artifact"), dict):
        transcript = message["artifact"].get("transcript", "")
    # Truncate to protect downstream pipeline
    transcript = sanitize_text(transcript, 8000)
    intent = detect_intent(transcript)
    intent_value = intent.get("intent") if isinstance(intent, dict) else str(intent)
    profile = lead_memory.build_profile(transcript)
    matches = match_properties(profile)

    lead_memory.upsert_lead(str(call_id), {"transcript": transcript, "intent": intent, "profile": profile})
    save_lead_profile(str(call_id), profile, transcript=transcript, intent=intent)

    booking_next_step = None
    if str(intent_value).lower() == "book_visit":
        booking_next_step = "collect_preferred_time"

    return JSONResponse({
        "status": "received",
        "call_id": call_id,
        "intent": intent_value,
        "intent_details": intent if isinstance(intent, dict) else {"raw": intent},
        "matched_properties": matches,
        "profile": profile,
        "transcript": transcript[:200],  # truncated for response
        "next_step": booking_next_step,
        "message": "Vapi webhook received successfully.",
    })


@app.post("/deepgram/webhook")
async def deepgram_webhook(request: Request):
    payload = await request.json()
    transcript = sanitize_text(payload.get("transcript", ""), 8000)
    intent = detect_intent(transcript)
    return {"status": "ok", "payload_received": bool(payload), "intent": intent}


# ===========================================================================
# Lead analysis & session state
# ===========================================================================
@app.post("/lead/analyze",
          dependencies=[Depends(require_api_key), Depends(rate_limit("default"))])
async def analyze_lead(request: Request):
    payload = await request.json()
    transcript = sanitize_text(payload.get("transcript", ""), 8000)
    session_id = sanitize_session_id(payload.get("session_id", "lead_analyze"))
    state = session_state.record_turn(session_id, transcript)
    profile = state.get("profile") or lead_memory.build_profile(transcript)
    matches = match_properties(profile)
    intent = detect_intent(transcript)
    lead_memory.upsert_lead(str(session_id), {"transcript": transcript, "intent": intent, "profile": profile})
    save_lead_profile(str(session_id), profile, transcript=transcript, intent=intent)

    return {
        "session_id": session_id,
        "profile": profile,
        "intent": intent,
        "session_state": state,
        "recommended_properties": matches,
    }


@app.post("/session/turn",
          dependencies=[Depends(require_api_key), Depends(rate_limit("default"))])
async def session_turn(payload: SessionTurnRequest):
    state = session_state.record_turn(payload.session_id, payload.transcript)
    profile = state.get("profile", {})
    intent = state.get("latest_intent", detect_intent(payload.transcript))
    return {
        "session_id": payload.session_id,
        "profile": profile,
        "intent": intent,
        "transcript_count": len(state.get("transcripts", [])),
        "session_state": state,
    }


# ===========================================================================
# Conversational agent (ML-powered, learns from chat history)
# ===========================================================================
@app.post("/agent/chat",
          dependencies=[Depends(require_api_key), Depends(rate_limit("chat"))])
def agent_chat(payload: ChatRequest):
    """Main chat endpoint. Uses LangGraph when available, or lightweight conversational fallback."""
    clean_session_id = sanitize_session_id(payload.session_id)
    clean_message = (payload.message or "").strip()

    if _LANGCHAIN_AVAILABLE and orchestrator is not None:
        try:
            result = orchestrator.process_turn(
                session_id=clean_session_id,
                transcript=clean_message,
            )
            # Extract assistant text
            assistant_text = ""
            for msg in reversed(result.get("messages", []) or []):
                msg_type = getattr(msg, "type", "") if not isinstance(msg, dict) else msg.get("type", msg.get("role", ""))
                if msg_type in ("ai", "assistant"):
                    content = (
                        getattr(msg, "content", None)
                        if not isinstance(msg, dict)
                        else msg.get("content")
                    )
                    if content and isinstance(content, str) and len(content.strip()) > 5:
                        assistant_text = content[:8000]
                        break
            if not assistant_text:
                profile = result.get("profile", {}) or {}
                recs = result.get("recommendations", []) or []
                city = profile.get("city") or "Lahore"
                area = profile.get("area") or ""
                location_str = f"{area} ({city})" if area and city else (area or city)

                if recs:
                    top = recs[0]
                    price_num = top.get("price", 0)
                    if price_num >= 10000000:
                        price_str = f"PKR {price_num / 10000000:g} crore"
                    elif price_num >= 100000:
                        price_str = f"PKR {price_num / 100000:g} lakh"
                    else:
                        price_str = f"PKR {price_num:,}"

                    prop_name = top.get("name", "Property")
                    assistant_text = (
                        f"Ji bilkul, hamare paas {location_str} mein behtareen options mojood hain, "
                        f"jaise ke {prop_name} ({price_str}). Kya aap is property ka visit schedule karna chahein ge ya mazeed options dekhna chahte hain?"
                    )
                elif location_str:
                    assistant_text = (
                        f"Ji bilkul, main {location_str} mein aap ke liye properties check kar rahi hoon. "
                        f"Aap ka andazan budget kitna hai aur kis type ya marla ki property talash kar rahe hain?"
                    )
                else:
                    assistant_text = (
                        "Main Real Estate Hub se Zara hoon. "
                        "Main aap ki property ki talash mein kis tarah madad kar sakti hoon? Aap kis shehar ya area mein dekh rahe hain?"
                    )

            strip_fn = strip_unwanted_greetings or fallback_strip_greetings
            assistant_text = strip_fn(assistant_text)

            # If visit/appointment is already booked, do not return property recommendations
            recs_to_send = result.get("recommendations", [])
            if result.get("appointment_details") or result.get("next_step") == "appointment_confirmed":
                recs_to_send = []

            return {
                "status": "ok",
                "session_id": clean_session_id,
                "reply": assistant_text,
                "intent": result.get("intent"),
                "profile": {k: v for k, v in (result.get("profile") or {}).items()
                            if k not in ("phone_number", "cnic", "email")},
                "recommendations": recs_to_send,
                "next_step": result.get("next_step"),
                "learned_context_used": result.get("learned_context_used", False),
                "confidence": result.get("confidence"),
            }
        except Exception as e:
            logger.warning("LangGraph orchestrator turn failed, using fallback: %s", e)

    # Seamless fallback processing on lightweight environments (e.g. Vercel Serverless)
    try:
        return process_chat_turn(session_id=clean_session_id, message=clean_message)
    except Exception as e:
        logger.exception("agent_chat fallback failed")
        return {
            "status": "ok",
            "session_id": clean_session_id,
            "reply": (
                "Main Real Estate Hub se Zara hoon. Main Lahore, Karachi, Islamabad aur Rawalpindi mein "
                "properties dhundne aur visit book karne mein aap ki madad kar sakti hoon. Aap kis area mein property talash kar rahe hain?"
            ),
            "intent": "lead_inquiry",
            "profile": {},
            "recommendations": [],
            "next_step": "followup",
            "learned_context_used": False,
            "confidence": 0.7,
        }


# ===========================================================================
# Agent memory (read-only, requires auth)
# ===========================================================================
@app.get("/agent/memory/stats",
         dependencies=[Depends(require_api_key), Depends(rate_limit("memory"))])
def agent_memory_stats():
    """Return corpus size and learned cluster count.
    Note: file paths are stripped to avoid info disclosure."""
    stats = conversation_learner.stats()
    stats.pop("memory_file", None)
    stats.pop("model_file", None)
    return stats


@app.get("/agent/memory/topics",
         dependencies=[Depends(require_api_key), Depends(rate_limit("memory"))])
def agent_memory_topics():
    """Return learned topic clusters (KMeans over past conversations).
    Sample queries are truncated to 120 chars to limit PII exposure."""
    topics = conversation_learner.get_topic_summary()
    # Truncate sample user queries for PII safety
    for t in topics:
        for s in t.get("samples", []):
            q = s.get("user_query", "")
            s["user_query"] = q[:120]
    return {"topics": topics}


@app.get("/agent/memory/similar",
         dependencies=[Depends(require_api_key), Depends(rate_limit("memory"))])
def agent_memory_similar(q: str, k: int = 3):
    """Find past conversations similar to query q. Truncates inputs and outputs."""
    q_safe = sanitize_text(q, 500)
    k = max(1, min(k, 10))
    results = conversation_learner.retrieve_similar(q_safe, k=k)
    # Truncate user_query / assistant_response in results
    for r in results:
        r["user_query"] = (r.get("user_query") or "")[:200]
        r["assistant_response"] = (r.get("assistant_response") or "")[:300]
    return {"query": q_safe[:80], "results": results}


@app.get("/agent/memory/templates",
         dependencies=[Depends(require_api_key), Depends(rate_limit("memory"))])
def agent_memory_templates(intent: Optional[str] = None, limit: int = 5):
    """Return highest-success assistant responses (optionally filtered by intent)."""
    limit = max(1, min(limit, 20))
    templates = conversation_learner.get_successful_templates(
        intent=sanitize_text(intent, 60) if intent else None,
        limit=limit,
    )
    # Truncate text fields
    for t in templates:
        t["user_query"] = (t.get("user_query") or "")[:200]
        t["assistant_response"] = (t.get("assistant_response") or "")[:300]
    return {"templates": templates}


@app.post("/agent/learn",
          dependencies=[Depends(require_admin_key), Depends(rate_limit("learn"))])
def agent_learn(payload: LearnRequest):
    """Manually teach the agent a conversation (admin only)."""
    result = conversation_learner.record_conversation(
        session_id=sanitize_session_id(payload.session_id),
        user_query=payload.user_query,
        assistant_response=payload.assistant_response,
        intent=sanitize_text(payload.intent, 60),
        outcome=sanitize_text(payload.outcome, 40) if payload.outcome else None,
        profile=payload.profile or {},
    )
    return result


@app.post("/agent/retrain",
          dependencies=[Depends(require_admin_key), Depends(rate_limit("retrain"))])
def agent_retrain():
    """Force a training pass (admin only)."""
    return conversation_learner.train()


# ===========================================================================
# Followups
# ===========================================================================
@app.post("/followups",
          dependencies=[Depends(require_api_key), Depends(rate_limit("default"))])
def create_followup(payload: FollowupRequest):
    """Create a followup task for a lead."""
    lead_id = sanitize_session_id(payload.lead_id)
    note = sanitize_text(payload.note, 2000)
    try:
        from datetime import datetime as dt
        scheduled = dt.fromisoformat(payload.scheduled_for)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid scheduled_for format") from e
    followup = {
        "id": f"fup_{uuid.uuid4().hex[:12]}",
        "lead_id": lead_id,
        "note": note,
        "scheduled_for": scheduled.isoformat(),
        "status": "pending",
        "created_at": now_iso(),
    }
    # Publish to n8n for downstream automation
    try:
        n8n_publisher.followup_created(
            followup_id=followup["id"],
            lead_id=lead_id,
            note=note,
            scheduled_for=scheduled.isoformat(),
        )
    except Exception as e:
        logger.warning(f"n8n publish failed: {e}")
    return followup


# ===========================================================================
# Admin / utilities
# ===========================================================================
@app.get("/admin/rate-limit/stats",
         dependencies=[Depends(require_admin_key)])
def rate_limit_stats():
    """Return current rate-limit bucket sizes (admin only)."""
    return {
        "buckets": {k: len(v) for k, v in rate_limiter._hits.items()},
        "limits": {k: v for k, v in __import__("app.services.security", fromlist=["RATE_LIMITS"]).RATE_LIMITS.items()},
    }


@app.delete("/admin/rate-limit/{ip}",
            dependencies=[Depends(require_admin_key)])
def reset_rate_limit(ip: str):
    """Reset rate-limit buckets for an IP (admin only)."""
    if not re.match(r"^[0-9a-fA-F.:]+$", ip):
        raise HTTPException(status_code=400, detail="Invalid IP")
    rate_limiter.reset(ip)
    return {"status": "reset", "ip": ip}

# Reload trigger for Vapi configuration update
