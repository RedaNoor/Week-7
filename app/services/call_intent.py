from typing import Dict, Any


def detect_intent(transcript: str) -> Dict[str, Any]:
    lower = (transcript or "").lower()

    if any(word in lower for word in ["book", "visit", "appointment", "schedule", "tour"]):
        return {"intent": "book_visit", "confidence": 0.9}
    if any(word in lower for word in ["price", "budget", "cost", "crore", "rupees", "payment"]):
        return {"intent": "price_inquiry", "confidence": 0.88}
    if any(word in lower for word in ["location", "area", "city", "near", "sector", "phase", "dha", "gulshan", "bahria"]):
        return {"intent": "location_inquiry", "confidence": 0.85}
    if "rent" in lower:
        return {"intent": "rental_inquiry", "confidence": 0.87}
    if any(word in lower for word in ["invest", "investment", "roi", "return"]):
        return {"intent": "investment_inquiry", "confidence": 0.9}
    if any(word in lower for word in ["family", "home", "house", "villa", "apartment"]):
        return {"intent": "property_search", "confidence": 0.74}
    return {"intent": "lead_inquiry", "confidence": 0.7}
