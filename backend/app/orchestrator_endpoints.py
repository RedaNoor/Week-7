"""
n8n-Ready Orchestration Endpoints

These FastAPI endpoints are designed to work with n8n workflows.
They accept n8n webhook payloads, process them with the LangGraph agent,
and return structured responses for n8n to consume.

Security: all endpoints require the admin API key (X-API-Key header).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.services.db_store_enhanced import (
    AppointmentStore,
    FollowupStore,
    LeadStore,
    SessionStore,
)
from app.services.langgraph_agent import orchestrator
from app.services.lead_memory import lead_memory
from app.services.n8n_webhook import n8n_publisher
from app.services.security import (
    rate_limit,
    require_admin_key,
    sanitize_session_id,
    sanitize_text,
)
from app.services.session_state import session_state

logger = logging.getLogger("orchestrator_endpoints")

router = APIRouter(prefix="/orchestrator", tags=["n8n orchestration"])


# ============================================================================
# Request Models (strict validation)
# ============================================================================


class N8NOrchestratorRequest(BaseModel):
    """Request from n8n to process a conversation turn."""
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1, max_length=80)
    lead_id: Optional[str] = Field(None, max_length=80)
    transcript: str = Field(..., min_length=1, max_length=8000)
    call_metadata: Optional[Dict[str, Any]] = None


class N8NLeadSyncRequest(BaseModel):
    """Request to sync lead data to Postgres."""
    model_config = ConfigDict(extra="forbid")

    lead_id: str = Field(..., min_length=1, max_length=80)
    phone_number: Optional[str] = Field(None, max_length=30)
    customer_name: Optional[str] = Field(None, max_length=120)
    profile: Dict[str, Any] = Field(default_factory=dict)
    transcript: Optional[str] = Field(None, max_length=8000)


class N8NAppointmentWebhookRequest(BaseModel):
    """Webhook confirmation from n8n after appointment creation in external system."""
    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(..., min_length=1, max_length=60)
    event_id: str = Field(..., min_length=1, max_length=80)
    lead_id: str = Field(..., min_length=1, max_length=80)
    appointment_id: Optional[str] = Field(None, max_length=80)
    status: str = Field(..., min_length=1, max_length=40)
    external_reference: Optional[str] = Field(None, max_length=200)
    timestamp: Optional[str] = Field(None, max_length=40)
    data: Optional[Dict[str, Any]] = None


class N8NFollowupRequest(BaseModel):
    """Request to create a followup task."""
    model_config = ConfigDict(extra="forbid")

    lead_id: str = Field(..., min_length=1, max_length=80)
    session_id: Optional[str] = Field(None, max_length=80)
    note: str = Field(..., min_length=1, max_length=2000)
    scheduled_for: str = Field(..., min_length=10, max_length=40)
    priority: Optional[str] = Field("normal", max_length=20)


# ============================================================================
# Endpoints (all require admin API key — these are service-to-service only)
# ============================================================================


@router.post("/process-turn",
             dependencies=[Depends(require_admin_key), Depends(rate_limit("default"))])
async def orchestrator_process_turn(request: N8NOrchestratorRequest) -> Dict[str, Any]:
    """Process a conversation turn through the LangGraph agent."""
    try:
        result = orchestrator.process_turn(
            session_id=sanitize_session_id(request.session_id),
            transcript=request.transcript,  # already length-bounded
        )

        session_state.record_turn(sanitize_session_id(request.session_id), request.transcript)

        lead_memory.upsert_lead(
            sanitize_session_id(request.lead_id or request.session_id),
            {
                "transcript": request.transcript,
                "profile": result.get("profile", {}),
                "intent": result.get("intent", "unknown"),
            },
        )

        if request.lead_id:
            try:
                n8n_publisher.lead_updated(
                    lead_id=request.lead_id,
                    profile=result.get("profile", {}),
                )
            except Exception as e:
                logger.warning(f"n8n publish failed: {e}")

        return {
            "status": "success",
            "session_id": request.session_id,
            "lead_id": request.lead_id,
            "result": result,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.exception("orchestrator_process_turn failed")
        return {
            "status": "error",
            "error": "internal_error",
            "session_id": request.session_id,
        }


@router.post("/sync-lead-to-postgres",
             dependencies=[Depends(require_admin_key), Depends(rate_limit("default"))])
async def sync_lead_to_postgres(request: N8NLeadSyncRequest) -> Dict[str, Any]:
    """Sync lead data from n8n to the Postgres database."""
    try:
        lead_id = sanitize_session_id(request.lead_id)

        result = LeadStore.create_or_update_lead(
            lead_id=lead_id,
            phone_number=sanitize_text(request.phone_number, 30) if request.phone_number else None,
            customer_name=sanitize_text(request.customer_name, 120) if request.customer_name else None,
            profile=request.profile or {},
        )

        lead_memory.upsert_lead(
            lead_id,
            {
                "profile": request.profile or {},
                "transcript": request.transcript or "",
            },
        )

        return {
            "status": "synced",
            "lead_id": lead_id,
            "phone_number": request.phone_number,
            "customer_name": request.customer_name,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.exception("sync_lead_to_postgres failed")
        return {
            "status": "error",
            "error": "internal_error",
            "lead_id": request.lead_id,
        }


@router.post("/n8n-webhook-confirmation",
             dependencies=[Depends(require_admin_key)])
async def n8n_webhook_confirmation(request: N8NAppointmentWebhookRequest) -> Dict[str, Any]:
    """Handle webhook confirmations from n8n workflows."""
    try:
        confirmation_log = {
            "event_type": request.event_type,
            "event_id": request.event_id,
            "lead_id": request.lead_id,
            "appointment_id": request.appointment_id,
            "status": request.status,
            "external_reference": request.external_reference,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }

        follow_up_action = None
        if request.event_type == "appointment_created":
            follow_up_action = {
                "type": "send_reminder",
                "lead_id": request.lead_id,
                "appointment_id": request.appointment_id,
            }
        elif request.event_type == "email_sent":
            follow_up_action = {
                "type": "log_communication",
                "lead_id": request.lead_id,
                "channel": "email",
            }
        elif request.event_type == "calendar_synced":
            follow_up_action = {
                "type": "send_confirmation",
                "lead_id": request.lead_id,
            }

        return {
            "status": "acknowledged",
            "event_type": request.event_type,
            "event_id": request.event_id,
            "confirmation_log": confirmation_log,
            "follow_up_action": follow_up_action,
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception:
        logger.exception("n8n_webhook_confirmation failed")
        return {
            "status": "error",
            "error": "internal_error",
            "event_id": request.event_id,
        }


@router.post("/create-followup",
             dependencies=[Depends(require_admin_key), Depends(rate_limit("default"))])
async def create_followup_from_n8n(request: N8NFollowupRequest) -> Dict[str, Any]:
    """Create a followup task (typically called by n8n workflows)."""
    try:
        followup_id = str(uuid.uuid4())

        followup_result = FollowupStore.create_followup(
            followup_id=followup_id,
            lead_id=sanitize_session_id(request.lead_id),
            session_id=sanitize_session_id(request.session_id) if request.session_id else None,
            note=sanitize_text(request.note, 2000),
            scheduled_for=request.scheduled_for,
            status="pending",
        )

        try:
            n8n_publisher.followup_created(
                followup_id=followup_id,
                lead_id=request.lead_id,
                note=request.note,
                scheduled_for=request.scheduled_for,
            )
        except Exception as e:
            logger.warning(f"n8n publish failed: {e}")

        return {
            "status": "created",
            "followup_id": followup_id,
            "lead_id": request.lead_id,
            "scheduled_for": request.scheduled_for,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception:
        logger.exception("create_followup_from_n8n failed")
        return {
            "status": "error",
            "error": "internal_error",
            "lead_id": request.lead_id,
        }


@router.get("/session/{session_id}/context",
            dependencies=[Depends(require_admin_key), Depends(rate_limit("default"))])
async def get_session_context(session_id: str) -> Dict[str, Any]:
    """Get full context for a session (admin only — exposes PII)."""
    try:
        session_id = sanitize_session_id(session_id)
        state = session_state.get_state(session_id)
        memory = lead_memory.get_lead(session_id)

        return {
            "status": "ok",
            "session_id": session_id,
            "session_state": state,
            "lead_memory": memory,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception:
        logger.exception("get_session_context failed")
        return {
            "status": "error",
            "error": "internal_error",
            "session_id": session_id,
        }


@router.get("/lead/{lead_id}/full-profile",
            dependencies=[Depends(require_admin_key), Depends(rate_limit("default"))])
async def get_lead_full_profile(lead_id: str) -> Dict[str, Any]:
    """Get the complete profile of a lead from Postgres and memory (admin only)."""
    try:
        lead_id = sanitize_session_id(lead_id)
        postgres_lead = LeadStore.fetch_lead(lead_id)
        memory_lead = lead_memory.get_lead(lead_id)

        combined_profile = {
            **(postgres_lead or {}),
            **(memory_lead or {}),
        }

        return {
            "status": "ok",
            "lead_id": lead_id,
            "profile": combined_profile,
            "source": "postgres+memory",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception:
        logger.exception("get_lead_full_profile failed")
        return {
            "status": "error",
            "error": "internal_error",
            "lead_id": lead_id,
        }
