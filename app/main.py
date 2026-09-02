from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from twilio.twiml.voice_response import VoiceResponse
import os

from app.config import settings
from app.services.call_intent import detect_intent
from app.services.lead_memory import lead_memory
from app.services.db_store import init_db, save_lead_profile, fetch_lead
from app.services.db_store_enhanced import init_db as init_enhanced_db
from app.services.property_matcher import match_properties
from app.services.session_state import session_state
from app.services.appointment_service import (
    cancel_appointment_record,
    create_appointment_record,
    list_appointments,
    reschedule_appointment_record,
)
from app.services.calendar_service import create_calendar_event
from app.services.crm_service import log_call_and_booking, create_crm_contact, log_activity
from app.services.email_service import send_booking_email, send_followup_email
from app.services.n8n_webhook import n8n_publisher
from app.services.langgraph_agent import orchestrator
from app.orchestrator_endpoints import router as orchestrator_router

app = FastAPI(title="Real Estate AI Voice Agent")

# init_db() and init_enhanced_db() both point at the same underlying schema
# now (see app/services/db_store.py), calling both is safe and just makes
# sure the tables exist regardless of which module runs first elsewhere.
try:
    init_db()
    init_enhanced_db()
except Exception as e:
    print(f"Database initialization warning: {e}")

# Include orchestrator endpoints for n8n integration
app.include_router(orchestrator_router)

# Enable CORS for dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AppointmentRequest(BaseModel):
    client_name: str
    client_phone: str
    property_id: str
    property_title: str
    scheduled_at: str
    employee_email: str | None = None


class RescheduleRequest(BaseModel):
    new_time: str


class SessionTurnRequest(BaseModel):
    session_id: str
    transcript: str


class OrchestratorRequest(BaseModel):
    """Request for LangGraph agent orchestrator."""
    session_id: str
    transcript: str
    lead_id: str | None = None


class N8NWebhookConfirmation(BaseModel):
    """Confirmation from n8n workflow."""
    event_id: str
    status: str
    timestamp: str | None = None
    data: dict | None = None


class FollowupRequest(BaseModel):
    """Request to create a followup task."""
    lead_id: str
    note: str
    scheduled_for: str


@app.get("/")
def healthcheck():
    return {"status": "ok", "app": settings.app_name, "capabilities": ["voice", "rag", "appointments"]}


@app.get("/dashboard")
async def serve_dashboard():
    """Serve the minimalist dashboard"""
    dashboard_path = os.path.join(os.path.dirname(__file__), "..", "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path, media_type="text/html")
    return {"error": "Dashboard not found"}


@app.get("/leads")
def get_leads():
    """Return all captured leads"""
    leads = []
    if hasattr(lead_memory, 'leads') and lead_memory.leads:
        for call_id, data in lead_memory.leads.items():
            profile = data.get("profile", {})
            location = ", ".join(part for part in [profile.get("area"), profile.get("city")] if part) or "N/A"
            leads.append({
                "id": call_id,
                "name": profile.get("customer_name") or "Unknown",
                "budget": profile.get("budget") or "N/A",
                "location": location,
                "property_type": profile.get("property_type") or "N/A",
                "intent": data.get("intent", "unknown"),
                "transcript": data.get("transcript", "")[:100],
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


@app.get("/appointments")
def get_appointments():
    """Return all appointments"""
    appointments = []
    for apt in list_appointments():
        appointments.append({
            "id": apt.get("appointment_id"),
            "client_name": apt.get("client_name", "Unknown"),
            "client_phone": apt.get("client_phone", "N/A"),
            "property_title": apt.get("property_title", "N/A"),
            "scheduled_at": apt.get("scheduled_at", "TBA"),
            "status": apt.get("status", "pending"),
        })
    return {"appointments": appointments}


@app.post("/twilio/voice")
async def twilio_voice(request: Request):
    form = await request.form()
    caller = form.get("From", "unknown caller")

    response = VoiceResponse()
    response.say(
        "Assalam-o-Alaikum. Welcome to RealEstate Hub. I am your virtual sales assistant. "
        "Please hold while I understand your requirements.",
        voice="Polly.Aditi",
        language="en-IN",
    )
    response.pause(length=1)
    response.say(f"Caller {caller} has reached the real-estate assistant.", voice="Polly.Aditi")

    return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/twilio/status")
async def twilio_status(request: Request):
    payload = await request.form()
    return JSONResponse({"status": "ok", "call_status": payload.get("CallStatus", "unknown")})


@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    payload = await request.json()

    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
    call = payload.get("call") if isinstance(payload.get("call"), dict) else {}
    call_id = payload.get("call_id") or payload.get("id") or call.get("id") or "unknown"
    transcript = payload.get("transcript") or message.get("transcript") or ""
    if not transcript and isinstance(message.get("artifact"), dict):
        transcript = message["artifact"].get("transcript", "")
    intent = detect_intent(transcript)
    intent_value = intent.get("intent") if isinstance(intent, dict) else str(intent)
    profile = lead_memory.build_profile(transcript)
    matches = match_properties(profile)

    lead_memory.upsert_lead(call_id, {"transcript": transcript, "intent": intent, "profile": profile})
    save_lead_profile(call_id, profile, transcript=transcript, intent=intent)

    # detect_intent() flags booking interest, but a real appointment needs a
    # confirmed date/time from the caller, which this webhook payload doesn't
    # have yet. Rather than writing a placeholder appointment with a fake
    # "To Be Scheduled" time, tell the caller (or the calling assistant) that
    # the next step is to collect a time and call POST /appointments once
    # there's a real scheduled_at value.
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
        "transcript": transcript,
        "next_step": booking_next_step,
        "message": "Vapi webhook received successfully."
    })


@app.post("/deepgram/webhook")
async def deepgram_webhook(request: Request):
    payload = await request.json()
    transcript = payload.get("transcript", "")
    intent = detect_intent(transcript)

    return {"status": "ok", "payload_received": bool(payload), "intent": intent}


@app.post("/lead/analyze")
async def analyze_lead(request: Request):
    payload = await request.json()
    transcript = payload.get("transcript", "")
    session_id = payload.get("session_id", "lead_analyze")
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


@app.post("/session/turn")
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


@app.post("/appointments")
def create_appointment(payload: AppointmentRequest):
    try:
        appointment = create_appointment_record(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
    )
    crm = log_call_and_booking(
        client_name=appointment["client_name"],
        phone=appointment["client_phone"],
        property_title=appointment["property_title"],
        status=appointment["status"],
    )
    return {"status": "created", "appointment": appointment, "calendar": calendar, "email": email, "crm": crm}


@app.put("/appointments/{appointment_id}")
def reschedule_appointment(appointment_id: str, payload: RescheduleRequest):
    try:
        appointment = reschedule_appointment_record(appointment_id, payload.new_time)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "updated", "appointment_id": appointment_id, "appointment": appointment}


@app.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: str):
    try:
        appointment = cancel_appointment_record(appointment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "cancelled", "appointment_id": appointment_id, "appointment": appointment}
