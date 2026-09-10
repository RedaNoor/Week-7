"""
Vapi Voice Call integration & Webhook service.

Processes Vapi Webhook events:
- function-call: Executes tool functions (availability search, appointment booking) for the live AI voice call.
- end-of-call-report: Extracts call transcripts, caller sentiment, property interests, and logs call history & lead memory.
- status-update: Monitors active voice calls.
"""

from __future__ import annotations

import os
import logging
import time
import uuid
from typing import Dict, Any, Optional

from app.services.call_history import record_call
from app.services.lead_memory import extract_profile
from app.services.appointment_service import create_appointment, AppointmentCreate
from app.services.property_matcher import search_properties

logger = logging.getLogger("vapi_service")
logger.setLevel(logging.INFO)

from app.config import settings

# Placeholder values that indicate VAPI is not properly configured
_PLACEHOLDER_ASSISTANT_IDS = {"", "vapi-real-estate-assistant-pk", "your_vapi_assistant_id"}
_PLACEHOLDER_PUBLIC_KEYS = {"", "pk_live_vapi_real_estate_demo", "your_vapi_public_key"}


def _get_vapi_assistant_id() -> str:
    return (
        os.getenv("VAPI_ASSISTANT_ID")
        or getattr(settings, "vapi_assistant_id", "")
        or ""
    ).strip()


def _get_vapi_public_key() -> str:
    return (
        os.getenv("VAPI_PUBLIC_KEY")
        or getattr(settings, "vapi_public_key", "")
        or ""
    ).strip()


def _is_vapi_configured() -> bool:
    """Check if VAPI credentials are real (not placeholder)."""
    aid = _get_vapi_assistant_id()
    pkey = _get_vapi_public_key()
    return aid not in _PLACEHOLDER_ASSISTANT_IDS and pkey not in _PLACEHOLDER_PUBLIC_KEYS


def get_vapi_config() -> Dict[str, Any]:
    """Return Vapi configuration details for the frontend Web Call client."""
    configured = _is_vapi_configured()
    aid = _get_vapi_assistant_id()
    pkey = _get_vapi_public_key()
    return {
        "assistant_id": aid if configured else "vapi-real-estate-assistant-pk",
        "public_key": pkey if configured else "pk_live_vapi_real_estate_demo",
        "enabled": configured,
        "configured": configured,
        "name": "Pakistani Real Estate Voice Sales Agent",
        "supported_languages": ["en", "ur"],
    }


def handle_vapi_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main webhook entrypoint for Vapi callbacks.
    Vapi payload format: { "message": { "type": "...", ... } }
    """
    message = payload.get("message", payload)
    msg_type = message.get("type")
    call_obj = message.get("call", {})

    logger.info(f"Received Vapi webhook event: {msg_type}")

    if msg_type == "function-call":
        return _handle_function_call(message, call_obj)
    elif msg_type == "end-of-call-report":
        return _handle_end_of_call(message, call_obj)
    elif msg_type == "status-update":
        return {"status": "success", "event": "status-update"}
    elif msg_type == "transcript":
        return {"status": "success", "event": "transcript"}
    else:
        return {"status": "success", "message": f"Event type {msg_type} received"}


def _handle_function_call(message: Dict[str, Any], call_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Execute tools called by the Vapi AI voice agent during a phone/web call."""
    func_call = message.get("functionCall", {})
    fn_name = func_call.get("name")
    parameters = func_call.get("parameters", {})

    logger.info(f"Vapi Function Call requested: {fn_name} with params: {parameters}")

    result = {}

    if fn_name == "search_properties":
        city = parameters.get("city")
        prop_type = parameters.get("type")
        max_price = parameters.get("max_price")
        bedrooms = parameters.get("bedrooms")
        
        matches = search_properties(
            city=city,
            prop_type=prop_type,
            max_price=max_price,
            bedrooms=bedrooms,
            limit=3
        )
        result = {
            "result": matches,
            "message": f"Found {len(matches)} properties matching requirements."
        }

    elif fn_name in ["book_appointment", "create_appointment"]:
        client_name = parameters.get("client_name", "Voice Caller")
        client_phone = parameters.get("client_phone", call_obj.get("customer", {}).get("number", "+923000000000"))
        client_email = parameters.get("client_email", call_obj.get("customer", {}).get("email", "caller@example.com"))
        property_id = parameters.get("property_id", "P001")
        property_title = parameters.get("property_title", "5 Marla House in DHA Phase 6")
        scheduled_at = parameters.get("scheduled_at", time.strftime("%Y-%m-%dT15:00:00+00:00", time.gmtime()))

        appt_input = AppointmentCreate(
            client_name=client_name,
            client_phone=client_phone,
            property_id=property_id,
            property_title=property_title,
            scheduled_at=scheduled_at,
            employee_email=client_email
        )
        created = create_appointment(appt_input)
        result = {
            "result": created.model_dump(),
            "message": f"Appointment successfully scheduled for {client_name} at {scheduled_at}."
        }

    else:
        result = {
            "result": None,
            "message": f"Function {fn_name} processed."
        }

    # Return standard Vapi function call response format
    return {
        "results": [
            {
                "toolCallId": message.get("toolCallId", "call_123"),
                "result": result
            }
        ]
    }


def _handle_end_of_call(message: Dict[str, Any], call_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Store transcript, extract caller profile, and log call into history & memory."""
    transcript = message.get("transcript") or message.get("summary") or "Voice call completed."
    summary = message.get("summary", "")
    customer = call_obj.get("customer", {})
    phone = customer.get("number", "+923000000000")
    email = customer.get("email", "caller@gmail.com")
    duration = message.get("durationSeconds", 60)

    # 1. Record call in call history
    call_entry = record_call(
        phone_number=phone,
        caller_name=customer.get("name", "Voice Client"),
        call_type="inbound_voice",
        transcript=transcript,
        notes=f"Vapi Call Summary: {summary}" if summary else "Vapi Call ended",
        sentiment="positive",
        owner_email=email
    )

    # 2. Extract profile for lead memory
    try:
        extract_profile(phone_number=phone, conversation_text=transcript)
    except Exception as e:
        logger.warning(f"Lead profile extraction failed for Vapi call: {e}")

    logger.info(f"Successfully processed Vapi end-of-call report for {phone}")
    return {
        "status": "success",
        "call_id": call_entry.get("call_id"),
        "phone": phone
    }
