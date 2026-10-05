"""
Lightweight Chat Agent Fallback for Zara (Real Estate Hub).

Handles chat interactions in Roman Urdu and English on environments
where full LangChain/LangGraph dependencies are omitted (e.g., Vercel Serverless).
Supports direct OpenAI/OpenRouter API completions if API keys are configured,
with an intelligent rule-based conversational fallback.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
import requests

from app.config import settings
from app.services.call_intent import detect_intent
from app.services.property_matcher import match_properties
from app.services.session_state import session_state
from app.services import profile_extraction

logger = logging.getLogger(__name__)


def strip_unwanted_greetings(text: str) -> str:
    """Remove redundant leading Assalam-o-Alaikum or greetings if duplicated."""
    if not text:
        return text
    pattern = r"^(?:(?:wal?aikum\s+)?assalam(?:u|\-o|\s+o|\s+u)?(?:\s+al[ae]y?kum)?|salam)[\!\,\.\s\-:]*"
    cleaned = re.sub(pattern, "", text.strip(), flags=re.IGNORECASE).strip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def _call_llm_if_available(message: str, history: List[str], profile: Dict[str, Any], recs: List[Dict[str, Any]]) -> Optional[str]:
    """Attempts direct OpenAI or OpenRouter completion if configured."""
    api_key = settings.openai_api_key or settings.openrouter_api_key
    if not api_key:
        return None

    is_openrouter = bool(settings.openrouter_api_key and not settings.openai_api_key)
    endpoint = (
        f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
        if is_openrouter
        else "https://api.openai.com/v1/chat/completions"
    )
    model = settings.openrouter_model if is_openrouter else "gpt-4o-mini"

    # Context string
    city = profile.get("city") or "Pakistan"
    recs_text = ""
    if recs:
        recs_text = "Matching Verified Listings:\n" + "\n".join(
            f"- {r.get('name')} in {r.get('location', '')} ({r.get('city', '')}) - Price: PKR {r.get('price', 0):,}"
            for r in recs[:3]
        )

    system_prompt = (
        "You are Zara, a friendly, professional AI Real Estate Consultant at Real Estate Hub in Pakistan. "
        "You communicate fluently and warmly in Roman Urdu / Urdulish (or English if the user speaks English). "
        "Help the user find properties, understand market prices, or book visits in cities like Lahore, Karachi, and Islamabad.\n"
        "Guidelines:\n"
        "- Keep replies concise, conversational, and natural (2 to 4 sentences).\n"
        "- Be polite, professional, and culturally aware.\n"
        f"User Profile: {profile}\n"
        f"{recs_text}\n"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-4:]:
        messages.append({"role": "user", "content": h})
    messages.append({"role": "user", "content": message})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if is_openrouter:
        headers["HTTP-Referer"] = "https://real-estate-hub.vercel.app"
        headers["X-Title"] = "Real Estate Hub Voice Agent"

    try:
        resp = requests.post(
            endpoint,
            headers=headers,
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 300,
            },
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            reply = data["choices"][0]["message"]["content"].strip()
            if reply:
                return reply
    except Exception as err:
        logger.warning("LLM direct call failed, falling back to rule-based dialogue: %s", err)

    return None


def generate_conversational_reply(message: str, profile: Dict[str, Any], intent_data: Dict[str, Any], recs: List[Dict[str, Any]]) -> str:
    """Intelligent Roman Urdu / English conversational responder."""
    lower = (message or "").lower().strip()
    intent = intent_data.get("intent", "lead_inquiry")

    # Greetings & Pleasantries
    if any(w in lower for w in ["salam", "assalam", "walaikum", "walaykum", "hello", "hi", "hey", "aoa", "kaise ho", "kya haal"]):
        return (
            "Walaikum Assalam! Main theek hoon, shukriya. Main Real Estate Hub se Zara hoon. "
            "Main aap ki property talash, price estimation ya appointment schedule karne mein kis tarah madad kar sakti hoon? "
            "Aap kis shehar (e.g. Lahore, Karachi, Islamabad) mein dekh rahe hain?"
        )

    # Booking / Appointments
    if intent == "book_visit" or any(w in lower for w in ["visit", "book", "appointment", "schedule", "milna", "dekhna chahta"]):
        city = profile.get("city") or "location"
        return (
            f"Ji zaroor! {city} mein visit schedule karne ke liye aap apna naam, phone number aur preferred date & time batayein, "
            "ya neeche diye gaye Appointment Booking form se direct instant booking kar lein."
        )

    # Price inquiries
    if intent == "price_inquiry" or any(w in lower for w in ["price", "cost", "rate", "qimat", "kitne", "crore", "lakh", "budget"]):
        city = profile.get("city") or "shehar"
        area = profile.get("area") or ""
        loc = f"{area}, {city}" if area and city != "shehar" else city
        return (
            f"Real Estate Hub par AI-powered price valuation tool dastiyab hai jo market trends ke mutabiq pricing batata hai. "
            f"Aap {loc} mein kis marla size ya property type ki exact valuation maloom karna chahte hain?"
        )

    # Location / Property Search
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
        loc_str = top.get("location", profile.get("city", "Pakistan"))
        return (
            f"Ji bilkul! Hamare paas {loc_str} mein behtareen verified options mojood hain, "
            f"jaise ke {prop_name} ({price_str}). Kya aap iska visit schedule karna chahein ge ya mazeed listings dekhna chahte hain?"
        )

    if profile.get("city") or profile.get("area"):
        loc = profile.get("area") or profile.get("city")
        return (
            f"Ji bilkul, main {loc} mein aap ke liye properties check kar rahi hoon. "
            "Aap ka andazan budget kitna hai aur aap ko kitne marla ya bedrooms ki property darkar hai?"
        )

    # General / Fallback
    return (
        "Main Real Estate Hub se Zara hoon. Main Lahore, Karachi, Islamabad aur Rawalpindi mein "
        "residential aur commercial properties dhundne aur appointment book karne mein aap ki mukammal madad kar sakti hoon. "
        "Aap kis shehar ya area mein invest ya rehaish dekh rahe hain?"
    )


def process_chat_turn(session_id: str, message: str) -> Dict[str, Any]:
    """Entry point for handling chat turns without LangGraph."""
    state = session_state.record_turn(session_id, message)
    profile = state.get("profile", {})
    intent_data = state.get("latest_intent", detect_intent(message))
    history = state.get("transcripts", [])

    # Match recommendations
    recs = match_properties(profile) or []

    # Attempt LLM completion first
    reply = _call_llm_if_available(message, history, profile, recs)
    if not reply:
        reply = generate_conversational_reply(message, profile, intent_data, recs)

    reply = strip_unwanted_greetings(reply)

    return {
        "status": "ok",
        "session_id": session_id,
        "reply": reply,
        "intent": intent_data.get("intent", "lead_inquiry"),
        "profile": {k: v for k, v in profile.items() if k not in ("phone_number", "cnic", "email")},
        "recommendations": recs[:3],
        "next_step": "followup",
        "learned_context_used": False,
        "confidence": intent_data.get("confidence", 0.85),
    }
