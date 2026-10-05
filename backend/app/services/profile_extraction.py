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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_ROOT = Path(__file__).resolve().parents[2]
_LOCATIONS_CSV = _ROOT / "data" / "locations.csv"

_CRORE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:crores?|cr|karor|kror)\b", re.IGNORECASE)
_LAKH_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:lakhs?|lacs?|lac|lk)\b", re.IGNORECASE)
_NAME_RE = re.compile(
    r"(?:my name is|mera naam|mera name|main naam|naam hai|naam|name is|i am|this is)\s*:?\s*([a-zA-Z]+(?:\s+[a-zA-Z]+)?)",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(r"(?:\+?92[-\s]?)?0?3\d{2}[-\s]?\d{7}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

_MONTH_MAP = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "october": 10,
    "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}


def _load_locations() -> list[Tuple[str, str]]:
    """Load (city, location_name) pairs from data/locations.csv.

    Uses the CSV ``name`` column (e.g. "DHA Phase 6") as the area
    identifier, because that is what properties.csv uses in its ``area``
    column.  Sorted by name length, longest first, so "DHA Phase 9 Prism"
    is matched before "DHA".
    """
    if not _LOCATIONS_CSV.exists():
        return []
    rows: list[Tuple[str, str]] = []
    with _LOCATIONS_CSV.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            city = (row.get("city") or "").strip()
            # Use 'name' column — that is the actual location identifier
            # (e.g. "DHA Phase 6", "Bahria Town Lahore") which matches
            # the 'area' field in properties.csv.
            location_name = (row.get("name") or "").strip()
            if city and location_name:
                rows.append((city, location_name))
    rows.sort(key=lambda pair: len(pair[1]), reverse=True)
    return rows


_LOCATIONS = _load_locations()
_CITIES = sorted({city for city, _ in _LOCATIONS}, key=len, reverse=True)


_MARLA_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:marla|marle)\b", re.IGNORECASE)
_KANAL_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:kanal)\b", re.IGNORECASE)


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


def extract_size_marla(text: str) -> Optional[float]:
    """Extract property size in Marla. 1 Kanal = 20 Marla."""
    match = _MARLA_RE.search(text)
    if match:
        return float(match.group(1))
    match = _KANAL_RE.search(text)
    if match:
        return float(match.group(1)) * 20.0
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
    return None, None


_BROAD_AREAS: list[Tuple[str, str, str]] = [
    # (keyword, default_city, broad_area_name)
    ("dha", "Lahore", "DHA"),
    ("bahria town", "Lahore", "Bahria Town"),
    ("bahria", "Lahore", "Bahria Town"),
    ("lake city", "Lahore", "Lake City Lahore"),
    ("eden housing", "Lahore", "Eden Housing"),
    ("eden", "Lahore", "Eden Housing"),
    ("gulberg greens", "Islamabad", "Gulberg Greens"),
    ("gulberg", "Lahore", "Gulberg"),
    ("johar town", "Lahore", "Johar Town"),
    ("model town", "Lahore", "Model Town"),
    ("wapda town", "Lahore", "Wapda Town"),
    ("askari", "Lahore", "Askari 11"),
    ("valencia", "Lahore", "Valencia Town"),
    ("clifton", "Karachi", "Clifton Block 5"),
    ("gulshan", "Karachi", "Gulshan-e-Iqbal Block 13-D"),
    ("north nazimabad", "Karachi", "North Nazimabad Block H"),
    ("faisal hills", "Islamabad", "Faisal Hills"),
    ("park view city", "Islamabad", "Park View City"),
    ("capital smart city", "Islamabad", "Capital Smart City"),
    ("sector g-11", "Islamabad", "Sector G-11"),
    ("g-11", "Islamabad", "Sector G-11"),
    ("sector f-11", "Islamabad", "Sector F-11"),
    ("f-11", "Islamabad", "Sector F-11"),
    ("sector i-8", "Islamabad", "Sector I-8"),
    ("i-8", "Islamabad", "Sector I-8"),
    ("sector d-12", "Islamabad", "Sector D-12"),
    ("d-12", "Islamabad", "Sector D-12"),
]


def extract_location(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Match against the real area/city catalog.
    
    1. Exact match on full location names (e.g. 'DHA Phase 6', 'Bahria Town Lahore').
    2. Broad area match (e.g. 'DHA', 'Bahria') preserving the broad category.
    3. City-only fallback if no area is recognized.
    """
    lower = text.lower()

    # Pass 1: exact match on full catalog location name
    exact = [(city, area) for city, area in _LOCATIONS if area.lower() in lower]
    if exact:
        return _disambiguate(exact, lower)

    # Find any mentioned city
    mentioned_city = None
    for city in _CITIES:
        if city.lower() in lower:
            mentioned_city = city
            break

    # Pass 2: broad area match (e.g. user said "DHA Lahore" or just "DHA")
    for keyword, default_city, broad_name in _BROAD_AREAS:
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, lower):
            city = mentioned_city or default_city
            return city, broad_name

    # Pass 3: city-only fallback
    if mentioned_city:
        return mentioned_city, None

    return None, None


def extract_property_type(text: str) -> Optional[str]:
    lower = text.lower()
    if "apartment" in lower or "flat" in lower:
        return "Apartment"
    if "villa" in lower or "house" in lower or "bungalow" in lower or "ghar" in lower or "makan" in lower:
        return "House"
    if "commercial" in lower or "shop" in lower or "office" in lower or "plaza" in lower or "dukaan" in lower:
        return "Commercial"
    if "plot" in lower or "land" in lower or "zameen" in lower:
        return "Plot"
    return None


def extract_purpose(text: str) -> Optional[str]:
    lower = text.lower()
    if any(word in lower for word in ["invest", "investment", "roi", "return", "sarmayakari", "munafa"]):
        return "Investment"
    if "rent" in lower or "rental" in lower or "kiraya" in lower or "kiraye" in lower:
        return "Rent"
    if any(word in lower for word in ["family", "home", "khandan", "rehne"]):
        return "Family"
    if any(word in lower for word in ["buy", "purchase", "wanted", "want", "looking for", "khareedna", "lena", "chahye", "chahiye"]):
        return "Buy"
    return None


def extract_customer_name(text: str) -> Optional[str]:
    match = _NAME_RE.search(text)
    if match:
        raw_name = match.group(1).strip()
        # Cut off any trailing conjunctions or contact indicators
        stop_words = [" or", " aur", " and", " phone", " email", " number", " hai", " hun", " hoon"]
        for stop in stop_words:
            if stop in raw_name.lower():
                raw_name = re.split(re.escape(stop), raw_name, flags=re.IGNORECASE)[0].strip()
        if len(raw_name) >= 2:
            return raw_name.title()
    return None


def extract_phone_number(text: str) -> Optional[str]:
    match = _PHONE_RE.search(text)
    if match:
        raw = re.sub(r"[^\d+]", "", match.group(0))
        if raw.startswith("0"):
            return "+92" + raw[1:]
        elif not raw.startswith("+"):
            return "+" + raw
        return raw
    return None


def extract_email(text: str) -> Optional[str]:
    match = _EMAIL_RE.search(text)
    if match:
        return match.group(0).strip().lower()
    return None


def extract_scheduled_at(text: str, existing_iso: Optional[str] = None) -> Optional[str]:
    """Parse appointment date/time from free text into ISO 8601 string."""
    lower = text.lower()
    now_utc = datetime.now(timezone.utc)
    base_date = None

    if existing_iso:
        try:
            base_date = datetime.fromisoformat(existing_iso).date()
        except (ValueError, TypeError):
            base_date = None

    # Date parsing
    target_date = None
    if "kal" in lower or "tomorrow" in lower:
        target_date = (now_utc + timedelta(days=1)).date()
    elif "parson" in lower or "day after tomorrow" in lower:
        target_date = (now_utc + timedelta(days=2)).date()
    elif "aaj" in lower or "today" in lower:
        target_date = now_utc.date()
    else:
        # e.g. "9 september 2026" or "9 september"
        m_date = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)(?:\s+(\d{4}))?", lower)
        if m_date and m_date.group(2) in _MONTH_MAP:
            day = int(m_date.group(1))
            month = _MONTH_MAP[m_date.group(2)]
            year = int(m_date.group(3)) if m_date.group(3) else now_utc.year
            try:
                target_date = datetime(year, month, day).date()
            except ValueError:
                target_date = None

    # Time parsing
    is_pm = any(w in lower for w in ["pm", "shaam", "raat", "dopahar", "sham"])
    is_am = any(w in lower for w in ["am", "subah"])
    target_hour = None
    target_minute = 0

    m_hour = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(?:bjy|baje|pm|am)\b", lower)
    if not m_hour:
        m_hour = re.search(r"\b(?:at|around)\s*(\d{1,2})(?::(\d{2}))?\b", lower)
    if not m_hour and (is_pm or is_am):
        m_hour = re.search(r"\b([1-9]|1[0-2])\b", lower)

    if m_hour:
        h = int(m_hour.group(1))
        target_minute = int(m_hour.group(2)) if m_hour.lastindex and m_hour.group(2) else 0
        if is_pm and h < 12:
            h += 12
        elif is_am and h == 12:
            h = 0
        target_hour = h

    # If neither date nor time found, return None
    if target_date is None and target_hour is None:
        return None

    # Merge with base date / existing time if partially specified
    final_date = target_date or base_date or (now_utc + timedelta(days=1)).date()
    final_hour = target_hour if target_hour is not None else 11

    final_dt = datetime(
        final_date.year, final_date.month, final_date.day,
        final_hour, target_minute, 0, tzinfo=timezone.utc
    )
    return final_dt.isoformat()


def extract_appointment_interest(text: str) -> bool:
    lower = text.lower()
    return any(word in lower for word in ["visit", "book", "appointment", "schedule", "tour", "chakkar", "milna"])


def empty_profile() -> Dict[str, Any]:
    return {
        "lead_id": "unknown",
        "customer_name": None,
        "phone_number": None,
        "email": None,
        "budget": None,
        "size_marla": None,
        "city": None,
        "area": None,
        "property_type": None,
        "purpose": None,
        "scheduled_at": None,
        "appointment_interest": False,
    }


def build_profile(transcript: str, existing_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Extract everything we can from a single transcript turn."""
    text = transcript or ""
    profile = empty_profile()

    profile["budget"] = extract_budget(text)
    profile["size_marla"] = extract_size_marla(text)
    city, area = extract_location(text)
    profile["city"] = city
    profile["area"] = area
    profile["property_type"] = extract_property_type(text)
    profile["purpose"] = extract_purpose(text)
    profile["customer_name"] = extract_customer_name(text)
    profile["phone_number"] = extract_phone_number(text)
    profile["email"] = extract_email(text)
    existing_scheduled = (existing_profile or {}).get("scheduled_at")
    profile["scheduled_at"] = extract_scheduled_at(text, existing_scheduled)
    profile["appointment_interest"] = extract_appointment_interest(text)

    return profile


_STICKY_FIELDS = {
    "budget", "size_marla", "city", "area", "property_type",
    "purpose", "customer_name", "phone_number", "email", "scheduled_at"
}
_EMPTY_VALUES = {"", "none", "unknown"}


def merge_profile(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Merge a newly extracted profile into the one built up over the call."""
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
