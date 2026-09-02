"""
n8n-Ready Orchestration Endpoints

These FastAPI endpoints are designed to work with n8n workflows.
They accept n8n webhook payloads, process them with the LangGraph agent,
and return structured responses for n8n to consume.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import uuid

from app.services.langgraph_agent import orchestrator
from app.services.n8n_webhook import n8n_publisher
from app.services.lead_memory import lead_memory
from app.services.session_state import session_state
from app.services.db_store_enhanced import (
    LeadStore,
    SessionStore,
    AppointmentStore,
    FollowupStore,
)

router = APIRouter(prefix="/orchestrator", tags=["n8n orchestration"])


# ============================================================================
# Request Models
# ============================================================================


class N8NOrchestratorRequest(BaseModel):
    """Request from n8n to process a conversation turn."""
    session_id: str
    lead_id: Optional[str] = None
    transcript: str
    call_metadata: Optional[Dict[str, Any]] = None


class N8NLeadSyncRequest(BaseModel):
    """Request to sync lead data to Postgres."""
    lead_id: str
    phone_number: Optional[str] = None
    customer_name: Optional[str] = None
    profile: Dict[str, Any]
    transcript: Optional[str] = None


class N8NAppointmentWebhookRequest(BaseModel):
    """Webhook confirmation from n8n after appointment creation in external system."""
    event_type: str  # "appointment_created", "appointment_cancelled", etc.
    event_id: str
    lead_id: str
    appointment_id: Optional[str] = None
    status: str
    external_reference: Optional[str] = None
    timestamp: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class N8NFollowupRequest(BaseModel):
    """Request to create a followup task."""
    lead_id: str
    session_id: Optional[str] = None
    note: str
    scheduled_for: str
    priority: Optional[str] = "normal"


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/process-turn")
async def orchestrator_process_turn(request: N8NOrchestratorRequest) -> Dict[str, Any]:
    """
    Process a conversation turn through the LangGraph agent.

    This endpoint:
    1. Processes the transcript through the LangGraph agent
    2. Updates session state and lead memory
    3. Publishes events to n8n for downstream processing
    4. Returns structured results

    Args:
        request: Orchestration request with session ID, lead ID, and transcript

    Returns:
        Agent response with profile, intent, recommendations, and next steps
    """
    try:
        # Use the orchestrator to process the turn
        result = orchestrator.process_turn(
            session_id=request.session_id,
            transcript=request.transcript,
        )

        # Update session state
        session_state.record_turn(request.session_id, request.transcript)

        # Upsert lead to memory
        lead_memory.upsert_lead(
            request.lead_id or request.session_id,
            {
                "transcript": request.transcript,
                "profile": result.get("profile", {}),
                "intent": result.get("intent", "unknown"),
            },
        )

        # Publish to n8n if lead ID is provided
        if request.lead_id:
            n8n_publisher.lead_updated(
                lead_id=request.lead_id,
                profile=result.get("profile", {}),
            )

        return {
            "status": "success",
            "session_id": request.session_id,
            "lead_id": request.lead_id,
            "result": result,
            "processed_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "session_id": request.session_id,
            "processed_at": datetime.utcnow().isoformat(),
        }


@router.post("/sync-lead-to-postgres")
async def sync_lead_to_postgres(request: N8NLeadSyncRequest) -> Dict[str, Any]:
    """
    Sync lead data from n8n to the Postgres database.

    This endpoint:
    1. Validates the profile data
    2. Creates or updates the lead in Postgres
    3. Saves transcript and intent data
    4. Returns confirmation

    Args:
        request: Lead sync request with profile and metadata

    Returns:
        Status and lead ID
    """
    try:
        lead_id = request.lead_id or str(uuid.uuid4())

        # Create or update lead in Postgres
        result = LeadStore.create_or_update_lead(
            lead_id=lead_id,
            phone_number=request.phone_number,
            customer_name=request.customer_name,
            profile=request.profile,
        )

        # Also update memory
        lead_memory.upsert_lead(
            lead_id,
            {
                "profile": request.profile,
                "transcript": request.transcript or "",
            },
        )

        return {
            "status": "synced",
            "lead_id": lead_id,
            "phone_number": request.phone_number,
            "customer_name": request.customer_name,
            "synced_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "lead_id": request.lead_id,
        }


@router.post("/n8n-webhook-confirmation")
async def n8n_webhook_confirmation(request: N8NAppointmentWebhookRequest) -> Dict[str, Any]:
    """
    Handle webhook confirmations from n8n workflows.

    This endpoint receives confirmations from n8n after it has:
    - Created calendar events
    - Sent emails
    - Synced with CRM systems
    - Created appointments in external systems

    Args:
        request: Webhook confirmation from n8n

    Returns:
        Acknowledgment and any follow-up actions
    """
    try:
        event_type = request.event_type
        lead_id = request.lead_id
        appointment_id = request.appointment_id

        # Log confirmation
        confirmation_log = {
            "event_type": event_type,
            "event_id": request.event_id,
            "lead_id": lead_id,
            "appointment_id": appointment_id,
            "status": request.status,
            "external_reference": request.external_reference,
            "received_at": datetime.utcnow().isoformat(),
        }

        # Trigger follow-up actions based on event type
        follow_up_action = None
        if event_type == "appointment_created":
            # Appointment was successfully created in external system
            follow_up_action = {
                "type": "send_reminder",
                "lead_id": lead_id,
                "appointment_id": appointment_id,
            }

        elif event_type == "email_sent":
            # Email was successfully sent
            follow_up_action = {
                "type": "log_communication",
                "lead_id": lead_id,
                "channel": "email",
            }

        elif event_type == "calendar_synced":
            # Calendar event was successfully created
            follow_up_action = {
                "type": "send_confirmation",
                "lead_id": lead_id,
            }

        return {
            "status": "acknowledged",
            "event_type": event_type,
            "event_id": request.event_id,
            "confirmation_log": confirmation_log,
            "follow_up_action": follow_up_action,
            "acknowledged_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "event_id": request.event_id,
        }


@router.post("/create-followup")
async def create_followup_from_n8n(request: N8NFollowupRequest) -> Dict[str, Any]:
    """
    Create a followup task (typically called by n8n workflows).

    This endpoint:
    1. Creates a followup record
    2. Stores it in Postgres
    3. Publishes events for reminder systems

    Args:
        request: Followup request with lead ID, note, and schedule

    Returns:
        Followup confirmation with ID
    """
    try:
        followup_id = str(uuid.uuid4())

        # Create followup in database
        followup_result = FollowupStore.create_followup(
            followup_id=followup_id,
            lead_id=request.lead_id,
            session_id=request.session_id,
            note=request.note,
            scheduled_for=request.scheduled_for,
            status="pending",
        )

        # Publish event to n8n
        n8n_publisher.followup_created(
            followup_id=followup_id,
            lead_id=request.lead_id,
            note=request.note,
            scheduled_for=request.scheduled_for,
        )

        return {
            "status": "created",
            "followup_id": followup_id,
            "lead_id": request.lead_id,
            "scheduled_for": request.scheduled_for,
            "created_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "lead_id": request.lead_id,
        }


@router.get("/session/{session_id}/context")
async def get_session_context(session_id: str) -> Dict[str, Any]:
    """
    Get full context for a session (for n8n to use in decisions).

    Returns:
        Complete session state including profile, transcript history, and intent

    Args:
        session_id: The session identifier

    Returns:
        Full session context
    """
    try:
        state = session_state.get_state(session_id)
        memory = lead_memory.get_lead(session_id)

        return {
            "status": "ok",
            "session_id": session_id,
            "session_state": state,
            "lead_memory": memory,
            "retrieved_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "session_id": session_id,
        }


@router.get("/lead/{lead_id}/full-profile")
async def get_lead_full_profile(lead_id: str) -> Dict[str, Any]:
    """
    Get the complete profile of a lead from Postgres and memory.

    This endpoint is useful for n8n workflows that need full lead context.

    Args:
        lead_id: The lead identifier

    Returns:
        Full lead profile from both Postgres and memory
    """
    try:
        # Get from Postgres
        postgres_lead = LeadStore.fetch_lead(lead_id)

        # Get from memory
        memory_lead = lead_memory.get_lead(lead_id)

        # Combine both
        combined_profile = {
            **(postgres_lead or {}),
            **(memory_lead or {}),
        }

        return {
            "status": "ok",
            "lead_id": lead_id,
            "profile": combined_profile,
            "source": "postgres+memory",
            "retrieved_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "lead_id": lead_id,
        }
