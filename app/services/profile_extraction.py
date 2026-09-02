"""
Shared lead-profile extraction and merge logic.

lead_memory, session_state, and the LangGraph orchestrator all need to turn
a raw transcript into the same budget/city/area/purpose fields. This module
is the single place that logic lives, so the three callers can't drift out
of sync with each other.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_ROOT = Path(__file__).resolve().parents[2]
_LOCATIONS_CSV = _ROOT / "data" / "locations.csv"

_CRORE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:crore|cr)\b", re.IGNORECASE)
_LAKH_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:lakh|lac)\b", re.IGNORECASE)
_NAME_RE = re.compile(
    r"(?:my name is|mera naam|main naam|naam)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)",
    re.IGNORECASE,
)


def _load_locations() -> list[Tuple[str, str]]:
    """Load (city, area) pairs from data/locations.csv.

    Sorted by area length, longest first, so a specific match like
    'DHA Phase 6' is checked before a shorter, more ambiguous one like 'DHA'.
    """
    if not _LOCATIONS_CSV.exists():
        return []
    rows: list[Tuple[str, str]] = []
    with _LOCATIONS_CSV.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            city = (row.get("city") or "").strip()
            area = (row.get("area") or "").strip()
            if city and area:
                rows.append((city, area))
    rows.sort(key=lambda pair: len(pair[1]), reverse=True)
    return rows


_LOCATIONS = _load_locations()
_CITIES = sorted({city for city, _ in _LOCATIONS}, key=len, reverse=True)


def extract_budget(text: str) -> Optional[str]:
    """Pull a budget figure out of free text, e.g. '3 crore', '4.5cr', '50 lakh'."""
    match = _CRORE_RE.search(text)
    if match:
        value = float(match.group(1))
        return f"{value:g} crore"
    match = _LAKH_RE.search(text)
    if match:
        value = float(match.group(1))
        return f"{value:g} lakh"
    return None


def _disambiguate(candidates: list[Tuple[str, str]], lower_text: str) -> Tuple[Optional[str], Optional[str]]:
    """Several cities can share an area name (Bahria Town exists in four of
    them). Prefer a candidate whose city is also named in the text; if the
    city was never said and the area name alone doesn't narrow it down to
    one city, keep the area but leave the city unset rather than guessing."""
    if not candidates:
        return None, None
    for city, area in candidates:
        if city.lower() in lower_text:
            return city, area
    cities = {city for city, _ in candidates}
    if len(cities) == 1:
        return candidates[0]
    # The area name alone doesn't tell us which city, and none was named.
    # Guessing one would be worse than leaving both unset.
    return None, None


def extract_location(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Match against the real area/city catalog instead of a fixed shortlist."""
    lower = text.lower()

    exact = [(city, area) for city, area in _LOCATIONS if area.lower() in lower]
    if exact:
        return _disambiguate(exact, lower)

    # Fall back to a loose match on the area's first word (e.g. someone says
    # just "DHA" without a phase or "Bahria" without "Town").
    words = set(re.findall(r"[a-z0-9\-]+", lower))
    loose = [(city, area) for city, area in _LOCATIONS if area.split()[0].lower() in words]
    if loose:
        return _disambiguate(loose, lower)

    for city in _CITIES:
        if city.lower() in lower:
            return city, None
    return None, None


def extract_property_type(text: str) -> Optional[str]:
    lower = text.lower()
    if "apartment" in lower or "flat" in lower:
        return "Apartment"
    if "villa" in lower or "house" in lower or "bungalow" in lower:
        return "House"
    if "commercial" in lower or "shop" in lower or "office" in lower or "plaza" in lower:
        return "Commercial"
    if "plot" in lower or "land" in lower:
        return "Plot"
    return None


def extract_purpose(text: str) -> Optional[str]:
    lower = text.lower()
    if any(word in lower for word in ["invest", "investment", "roi", "return"]):
        return "invest"
    if "rent" in lower or "rental" in lower:
        return "rent"
    if any(word in lower for word in ["buy", "purchase", "wanted", "want", "looking for"]):
        return "buy"
    if any(word in lower for word in ["family", "home", "house"]):
        return "Family"
    return None


def extract_customer_name(text: str) -> Optional[str]:
    match = _NAME_RE.search(text)
    if match:
        return match.group(1).strip().title()
    return None


def extract_appointment_interest(text: str) -> bool:
    lower = text.lower()
    return any(word in lower for word in ["visit", "book", "appointment", "schedule", "tour"])


def empty_profile() -> Dict[str, Any]:
    return {
        "lead_id": "unknown",
        "customer_name": None,
        "budget": None,
        "city": None,
        "area": None,
        "property_type": None,
        "purpose": None,
        "appointment_interest": False,
    }


def build_profile(transcript: str) -> Dict[str, Any]:
    """Extract everything we can from a single transcript turn."""
    text = transcript or ""
    profile = empty_profile()

    profile["budget"] = extract_budget(text)
    city, area = extract_location(text)
    profile["city"] = city
    profile["area"] = area
    profile["property_type"] = extract_property_type(text)
    profile["purpose"] = extract_purpose(text)
    profile["customer_name"] = extract_customer_name(text)
    profile["appointment_interest"] = extract_appointment_interest(text)

    return profile


_STICKY_FIELDS = {"budget", "city", "area", "property_type", "purpose", "customer_name"}
_EMPTY_VALUES = {"", "none", "unknown"}


def merge_profile(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Merge a newly extracted profile into the one built up over the call.

    The newest non-empty value wins for the core fields, since a caller
    correcting themselves ("actually, 2 crore not 3") should update the
    profile rather than being ignored. appointment_interest only turns on,
    never back off.
    """
    merged = dict(existing) if existing else empty_profile()
    for key, value in (incoming or {}).items():
        if value is None:
            continue
        if key == "appointment_interest":
            merged[key] = bool(merged.get(key)) or bool(value)
        elif key in _STICKY_FIELDS:
            if str(value).strip().lower() not in _EMPTY_VALUES:
                merged[key] = value
        else:
            merged[key] = value
    return merged
