"""
Lightweight, Production-Grade Chat Agent for Zara (Real Estate Hub).

Handles chat interactions in Roman Urdu and English on environments
where full LangGraph dependencies are omitted (e.g., Vercel Serverless).
Supports direct OpenRouter / OpenAI API completions with a sophisticated system prompt grounded
in the real property catalog dataset, and includes an intelligent rule-based conversational fallback.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional
import requests

from app.config import settings
from app.services.call_intent import detect_intent
from app.services.property_matcher import PROPERTY_CATALOG, match_properties
from app.services.session_state import session_state
from app.services import profile_extraction

logger = logging.getLogger(__name__)


def strip_unwanted_greetings(text: str, is_ongoing: bool = False) -> str:
    """Remove redundant leading Assalam-o-Alaikum or greetings if duplicated."""
    if not text:
        return text
    if is_ongoing:
        pattern = r"^(?:(?:wal?aikum\s+)?assalam(?:u|\-o|\s+o|\s+u)?(?:\s+al[ae]y?kum)?|salam|khushamdeed|khush\s*aamdeed|aap\s*ka\s*swagat\s*hai|swagat\s*hai)[\!\,\.\s\-:]*"
        cleaned = re.sub(pattern, "", text.strip(), flags=re.IGNORECASE).strip()
    else:
        pattern = r"^(?:(?:wal?aikum\s+)?assalam(?:u|\-o|\s+o|\s+u)?(?:\s+al[ae]y?kum)?|salam)[\!\,\.\s\-:]*"
        cleaned = re.sub(pattern, "", text.strip(), flags=re.IGNORECASE).strip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned or text


def _call_llm_if_available(message: str, history: List[str], profile: Dict[str, Any], recs: List[Dict[str, Any]]) -> Optional[str]:
    """Attempts direct OpenRouter or OpenAI completion grounded in the real catalog."""
    openrouter_key = settings.openrouter_api_key or os.environ.get("OPENROUTER_API_KEY", "")
    openai_key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY", "")

    api_key = openrouter_key or openai_key
    if not api_key:
        return None

    is_openrouter = bool(openrouter_key)
    endpoint = (
        f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
        if is_openrouter
        else "https://api.openai.com/v1/chat/completions"
    )
    model = settings.openrouter_model if is_openrouter else "gpt-4o-mini"

    # Contextual catalog options
    city = profile.get("city")
    available_catalog = [p for p in PROPERTY_CATALOG if not city or p.get("city", "").lower() == city.lower()]
    catalog_text = "Verified Property Catalog:\n" + "\n".join(
        f"- ID: {p.get('property_id')} | {p.get('name')} | Type: {p.get('type')} in {p.get('area')}, {p.get('city')} | Size: {p.get('size_marla')} Marla | Price: PKR {p.get('price', 0):,} ({p.get('price', 0)/10000000:.2f} Crore / {p.get('price', 0)/100000:.1f} Lakh)"
        for p in available_catalog[:25]
    )

    is_ongoing_convo = len(history) >= 2

    system_prompt = (
        "You are Zara, a highly professional, courteous, and knowledgeable female AI Real Estate Consultant at Real Estate Hub in Pakistan.\n"
        "You communicate fluently and naturally in Pakistani Roman Urdu / Urdulish (or English if the user speaks English).\n\n"
        "CRITICAL BEHAVIORAL RULES:\n"
        f"1. GREETING RULE (NO REPEATING 'Khushamdeed'): This conversation is {'ONGOING (turn ' + str(len(history)) + ')' if is_ongoing_convo else 'STARTING'}. "
        "DO NOT start your response with 'Khushamdeed', 'Aap kaise hain', or greetings in ongoing turns! Only greet on turn 1 if the user said hello/salam. In ongoing conversation, answer directly and helpfully.\n"
        "2. STRICT BUDGET & DATASET COMPLIANCE: You MUST ONLY recommend and discuss properties from the provided Verified Property Catalog that fit within the user's stated budget! "
        "Never recommend a 4.5 crore or 9 crore house if the user's budget is 2 crore (20,000,000 PKR). "
        "If a user wants DHA Lahore with a 2 crore budget, explain clearly that houses in DHA Phase 6 start at 4.5 crore, but they can get a 5 Marla Plot in DHA Phase 9 Prism for PKR 1.45 crore (14,500,000), or a 5 Marla House in Eden Housing Lahore for PKR 1.85 crore (18,500,000) within their budget.\n"
        "3. PROPERTY DISCOVERY: If the user says 'property talash' without a city or budget, ask which city (Lahore, Karachi, Islamabad) and what budget/size they prefer.\n"
        "4. STRICT GUARDRAIL: Only discuss Pakistani real estate. Decline off-topic queries politely.\n"
        "5. STYLE: Warm, polite, concise (2 to 4 sentences), accurate prices.\n\n"
        f"User Profile so far: {profile}\n"
        f"{catalog_text}\n"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-6:]:
        messages.append({"role": "user", "content": h})
    messages.append({"role": "user", "content": message})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if is_openrouter:
        headers["HTTP-Referer"] = "https://real-estate-hub-fawn.vercel.app"
        headers["X-Title"] = "Real Estate Hub Voice Agent"

    try:
        resp = requests.post(
            endpoint,
            headers=headers,
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.6,
                "max_tokens": 320,
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

    # Asking how the bot is doing
    if any(w in lower for w in ["kaise ho", "kya haal", "kaisi ho", "kaisi hain", "how are you"]):
        return (
            "Alhamdulillah, main theek hoon, shukriya! Main Real Estate Hub se Zara hoon. "
            "Main aap ki property talash, market valuation ya appointment booking mein kis tarah madad kar sakti hoon?"
        )

    # Simple Greetings
    if any(w in lower for w in ["salam", "assalam", "walaikum", "walaykum", "hello", "hi", "hey", "aoa"]):
        return (
            "Walaikum Assalam! Main Real Estate Hub se Zara hoon. "
            "Main aap ki property ki talash, market rates ya visit booking mein kis tarah madad kar sakti hoon? "
            "Aap kis shehar ya area mein property dekh rahe hain?"
        )

    # City / Clarification Questions
    if any(w in lower for w in ["kis city", "kon si city", "konsi city", "konsa shehar", "which city", "what none", "kahan ki"]):
        return (
            "Main Pakistan ke major shehron jese Lahore, Karachi, Islamabad aur Rawalpindi mein verified properties ki baat kar rahi hoon. "
            "Aap kis specific shehar ya area (jaise DHA, Bahria Town, Gulshan, Eden Housing) mein property talash karna chahte hain?"
        )

    # Off-topic Guardrail
    if any(w in lower for w in ["weather", "mausam", "cricket", "match", "politics", "siyasat", "recipe", "cooking", "code", "programming", "python", "movie"]):
        return (
            "Main Real Estate Hub ki AI property consultant hoon. Main sirf Pakistan mein properties ki khareed o farokht, rent, market rates aur visit booking se mutalliq madad kar sakti hoon. "
            "Kya aap koi property talash kar rahe hain ya kisi location ki pricing jan-na chahte hain?"
        )

    # Booking / Appointments
    if intent == "book_visit" or any(w in lower for w in ["visit", "book", "appointment", "schedule", "milna", "dekhna chahta"]):
        city_name = profile.get("city") or "property"
        return (
            f"Ji bilkul! {city_name} mein visit schedule karne ke liye aap apna naam, contact number aur preferred date & time batayein, "
            "ya page par diye gaye Appointment Booking section se instant book kar lein."
        )

    # Budget & Sasta options request
    if any(w in lower for w in ["sasta", "sasti", "kam price", "mehnga", "mehngi", "budget kam", "low budget"]):
        city = profile.get("city") or "Lahore"
        return (
            f"{city} mein 2 crore ke budget ke andar hamare paas behtareen options hain: "
            "1. 5 Marla House in Eden Housing Lahore (PKR 1.85 crore / 18,500,000)\n"
            "2. 5 Marla Plot in DHA Phase 9 Prism (PKR 1.45 crore / 14,500,000)\n"
            "3. 2 Bed Apartment in Gulberg Lahore (PKR 1.25 crore / 12,500,000)\n"
            "Kya aap in mein se kisi ka visit schedule karna chahenge?"
        )

    # Property Search with specific city provided
    city = profile.get("city")
    if city and recs:
        top = recs[0]
        price_num = top.get("price", 0)
        if price_num >= 10000000:
            price_str = f"PKR {price_num / 10000000:g} crore"
        elif price_num >= 100000:
            price_str = f"PKR {price_num / 100000:g} lakh"
        else:
            price_str = f"PKR {price_num:,}"

        prop_name = top.get("name", "Property")
        area_str = top.get("area") or city
        return (
            f"Hamare paas {city} ({area_str}) mein aap ke budget ke mutabiq verified options mojood hain, "
            f"jaise ke {prop_name} ({price_str}). Kya aap is property ka visit schedule karna chahein ge ya mazeed listings dekhna chahte hain?"
        )

    # Property Search without city specified
    if intent == "property_search" or any(w in lower for w in ["property talash", "property", "ghar", "flat", "plot", "makan", "house", "apartment", "investment"]):
        return (
            "Hamare paas Lahore, Karachi, Islamabad aur Rawalpindi mein verified houses, plots aur flats mojood hain. "
            "Aap kis shehar mein dekh rahe hain, aur aap ka andazan budget ya required size (e.g. 5 Marla, 10 Marla) kya hai?"
        )

    # General / Default Fallback
    return (
        "Main Lahore, Karachi, Islamabad aur Rawalpindi mein "
        "residential o commercial properties talash karne aur visit schedule karne mein aap ki madad kar sakti hoon. "
        "Aap kis shehar ya area mein property dekh rahe hain?"
    )


def process_chat_turn(session_id: str, message: str) -> Dict[str, Any]:
    """Entry point for handling chat turns."""
    state = session_state.record_turn(session_id, message)
    profile = state.get("profile", {})
    intent_data = state.get("latest_intent", detect_intent(message))
    history = state.get("transcripts", [])
    is_ongoing = len(history) >= 2

    # Match recommendations strictly using parsed profile
    matched = match_properties(profile) or []

    # Attempt LLM completion first
    reply = _call_llm_if_available(message, history, profile, matched)
    if not reply:
        reply = generate_conversational_reply(message, profile, intent_data, matched)

    reply = strip_unwanted_greetings(reply, is_ongoing=is_ongoing)

    # Only attach recommendations to UI if the user has specified a city or area
    user_specified_location = bool(profile.get("city") or profile.get("area"))
    recs_to_send = matched[:3] if user_specified_location else []

    return {
        "status": "ok",
        "session_id": session_id,
        "reply": reply,
        "intent": intent_data.get("intent", "lead_inquiry"),
        "profile": {k: v for k, v in profile.items() if k not in ("phone_number", "cnic", "email")},
        "recommendations": recs_to_send,
        "next_step": "followup",
        "learned_context_used": False,
        "confidence": intent_data.get("confidence", 0.85),
    }
