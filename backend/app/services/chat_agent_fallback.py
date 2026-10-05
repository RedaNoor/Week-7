"""
Lightweight, Production-Grade Chat Agent for Zara (Real Estate Hub).

Handles chat interactions in Roman Urdu and English on environments
where full LangGraph dependencies are omitted (e.g., Vercel Serverless).
Supports direct OpenRouter / OpenAI API completions with a sophisticated system prompt,
and includes an intelligent, culturally-aware rule-based conversational fallback with strict guardrails.
"""

from __future__ import annotations

import logging
import os
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
    """Attempts direct OpenRouter or OpenAI completion if configured."""
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

    # Format recommendations for LLM context
    recs_text = ""
    city = profile.get("city")
    if recs and city:
        recs_text = "Verified Listings Available:\n" + "\n".join(
            f"- {r.get('name')} in {r.get('area', '')} ({r.get('city', '')}) - Price: PKR {r.get('price', 0):,}"
            for r in recs[:3]
        )

    system_prompt = (
        "You are Zara, a highly professional, courteous, and knowledgeable female AI Real Estate Consultant at Real Estate Hub in Pakistan.\n"
        "You communicate fluently and naturally in Pakistani Roman Urdu / Urdulish (or English if the user speaks English).\n\n"
        "Behavioral Rules:\n"
        "1. Language & Vocabulary: Use authentic Pakistani Urdu vocabulary (e.g., 'Khushamdeed', 'Ji', 'Shukriya', 'Walaikum Assalam', 'Ghar', 'Dastiyab', 'Khareed o Farokht'). Do NOT use Hindi words like 'Swagat' or 'Namaste'. Speak with female gender inflections in Urdu (e.g. 'kar sakti hoon', 'bata sakti hoon').\n"
        "2. Greeting Response: When the user greets you ('Walaikum Assalam', 'Salam', 'Hello', etc.), warmly acknowledge and ask how you can assist with their real estate needs. Do NOT say 'Main theek hoon' unless the user explicitly asks how you are doing ('kaise ho', 'kya haal hai').\n"
        "3. Property Discovery: When the user expresses interest in properties ('property talash', 'ghar dekhna hai', 'plots', etc.) WITHOUT mentioning a city or budget, ask clarifying questions first: 'Aap kis shehar (jaise Lahore, Karachi, Islamabad) mein dekh rahe hain, aur aap ka andazan budget ya required size (e.g. 5 Marla, 10 Marla, Flat) kya hai?'\n"
        "4. Specificity & Clarity: Never say 'None' or use placeholders. When discussing locations, refer to real places (DHA, Bahria Town, Gulshan, Gulberg, G-10, E-11, etc.). If the user asks which city you mean, clarify that Real Estate Hub serves Lahore, Karachi, Islamabad, and Rawalpindi.\n"
        "5. Strict Real Estate Guardrails: You only assist with Pakistani real estate (buying, selling, renting, market price valuation, booking visits). If the user asks about unrelated topics (politics, sports, coding, cooking, weather), politely decline and bring the conversation back to real estate.\n"
        "6. Style: Keep responses warm, respectful, concise (2 to 4 sentences), and professional.\n\n"
        f"Extracted User Profile: {profile}\n"
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
        headers["HTTP-Referer"] = "https://real-estate-hub-fawn.vercel.app"
        headers["X-Title"] = "Real Estate Hub Voice Agent"

    try:
        resp = requests.post(
            endpoint,
            headers=headers,
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.65,
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

    # Asking how the bot is doing
    if any(w in lower for w in ["kaise ho", "kya haal", "kaisi ho", "kaisi hain", "how are you"]):
        return (
            "Alhamdulillah, main theek hoon, shukriya! Main Real Estate Hub se Zara hoon. "
            "Main aap ki property talash, market valuation ya appointment booking mein kis tarah madad kar sakti hoon?"
        )

    # Simple Greetings & Pleasantries (User did not ask how the bot is)
    if any(w in lower for w in ["salam", "assalam", "walaikum", "walaykum", "hello", "hi", "hey", "aoa"]):
        return (
            "Walaikum Assalam! Main Real Estate Hub se Zara hoon. "
            "Main aap ki property ki talash, market rates ya visit booking mein kis tarah madad kar sakti hoon? "
            "Aap kis shehar ya area mein property dekh rahe hain?"
        )

    # City / Clarification Questions ("kis city ki bat", "which city", "what none", "shehar")
    if any(w in lower for w in ["kis city", "kon si city", "konsi city", "konsa shehar", "which city", "what none", "kahan ki"]):
        return (
            "Main Pakistan ke major shehron jese Lahore, Karachi, Islamabad aur Rawalpindi mein verified properties ki baat kar rahi hoon. "
            "Aap kis specific shehar ya area (jaise DHA, Bahria Town, Gulshan, G-11) mein property talash karna chahte hain?"
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

    # Price inquiries
    if intent == "price_inquiry" or any(w in lower for w in ["price", "cost", "rate", "qimat", "kitne", "crore", "lakh", "budget"]):
        city = profile.get("city")
        area = profile.get("area")
        if city or area:
            loc = f"{area}, {city}" if area and city else (area or city)
            return (
                f"Real Estate Hub par AI-powered price valuation tool dastiyab hai jo latest market trends ke mutabiq rates calculate karta hai. "
                f"Aap {loc} mein kis marla size (e.g. 5 Marla, 10 Marla, 1 Kanal) ki valuation maloom karna chahte hain?"
            )
        return (
            "Real Estate Hub par machine-learning price valuation tool mojood hai. "
            "Aap kis shehar aur location (e.g. DHA Lahore, Bahria Karachi, Islamabad) ki property ka rate jan-na chahte hain?"
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
            f"Ji bilkul! Hamare paas {city} ({area_str}) mein behtareen verified options mojood hain, "
            f"jaise ke {prop_name} ({price_str}). Kya aap is property ka visit schedule karna chahein ge ya mazeed listings dekhna chahte hain?"
        )

    # Property Search without city specified (e.g. "property talash", "ghar dekhna hai")
    if intent == "property_search" or any(w in lower for w in ["property talash", "property", "ghar", "flat", "plot", "makan", "house", "apartment", "investment"]):
        return (
            "Ji bilkul! Hamare paas Lahore, Karachi, Islamabad aur Rawalpindi mein verified houses, plots aur flats mojood hain. "
            "Aap kis shehar mein dekh rahe hain, aur aap ka andazan budget ya required size (e.g. 5 Marla, 10 Marla) kya hai?"
        )

    # General / Default Fallback
    return (
        "Main Real Estate Hub se Zara hoon. Main Lahore, Karachi, Islamabad aur Rawalpindi mein "
        "residential o commercial properties talash karne aur visit schedule karne mein aap ki madad kar sakti hoon. "
        "Aap kis shehar ya area mein property dekh rahe hain?"
    )


def process_chat_turn(session_id: str, message: str) -> Dict[str, Any]:
    """Entry point for handling chat turns."""
    state = session_state.record_turn(session_id, message)
    profile = state.get("profile", {})
    intent_data = state.get("latest_intent", detect_intent(message))
    history = state.get("transcripts", [])

    # Match recommendations
    matched = match_properties(profile) or []

    # Attempt LLM completion first
    reply = _call_llm_if_available(message, history, profile, matched)
    if not reply:
        reply = generate_conversational_reply(message, profile, intent_data, matched)

    reply = strip_unwanted_greetings(reply)

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
