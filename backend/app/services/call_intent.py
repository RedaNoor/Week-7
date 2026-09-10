from typing import Dict, Any


def detect_intent(transcript: str) -> Dict[str, Any]:
    lower = (transcript or "").lower()

    # Explicit appointment / booking requests
    if any(word in lower for word in ["appointment", "schedule", "visit book", "appointment book", "visit schedule", "tour book", "booking"]):
        return {"intent": "book_visit", "confidence": 0.95}
    if any(phrase in lower for phrase in ["appointment krdain", "appointment kr dein", "appointment kar dein", "appointment rakh dein", "visit rakh dein", "visit karni hai", "visit karna hai", "milna hai", "chakkar lagana"]):
        return {"intent": "book_visit", "confidence": 0.95}
    if "book" in lower and not any(w in lower for w in ["facebook", "brochure", "booklet"]):
        return {"intent": "book_visit", "confidence": 0.9}

    if any(word in lower for word in ["price", "budget", "cost", "crore", "rupees", "payment", "qimat", "keemat", "paisa", "kitne", "kitna", "rate", "lakh"]):
        return {"intent": "price_inquiry", "confidence": 0.88}
    if any(word in lower for word in ["location", "area", "city", "near", "sector", "phase", "dha", "gulshan", "bahria", "kahan", "jagah", "shehar"]):
        return {"intent": "location_inquiry", "confidence": 0.85}
    if any(word in lower for word in ["rent", "rental", "kiraya", "kiraye"]):
        return {"intent": "rental_inquiry", "confidence": 0.87}
    if any(word in lower for word in ["invest", "investment", "roi", "return", "sarmayakari", "munafa", "faida"]):
        return {"intent": "investment_inquiry", "confidence": 0.9}
    if any(word in lower for word in ["family", "home", "house", "villa", "apartment", "ghar", "makan", "flat", "plot", "kothi", "dekhna", "dekhne", "dikha", "dikhayein", "dikhao", "dikha dain"]):
        return {"intent": "property_search", "confidence": 0.8}
    return {"intent": "lead_inquiry", "confidence": 0.7}
