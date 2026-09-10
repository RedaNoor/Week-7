"""
Property catalog loader and matcher.

Loads the property catalog from `data/properties.csv` and exposes:
- PROPERTY_CATALOG: the full list (loaded at import time)
- match_properties(profile): returns up to 3 properties matching the
  customer's stated budget / city / area / property type / purpose

The CSV schema is:
    property_id, name, developer, city, area, type,
    bedrooms, size_sqft, size_marla, price, status, purpose
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("property_matcher")

# parents[0] = app/services, parents[1] = app, parents[2] = project root
ROOT = Path(__file__).resolve().parents[2]
PROPERTY_CATALOG: List[Dict[str, Any]] = []


def _load_catalog() -> List[Dict[str, Any]]:
    catalog_path = ROOT / "data" / "properties.csv"
    if not catalog_path.exists():
        logger.warning(f"properties.csv not found at {catalog_path}")
        return []

    items: List[Dict[str, Any]] = []
    with catalog_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            price_raw = (row.get("price") or "0").replace(",", "")
            try:
                price = int(float(price_raw))
            except ValueError:
                price = 0

            try:
                beds = int(row.get("bedrooms") or 0)
            except ValueError:
                beds = 0

            try:
                size_sqft = int(float(row.get("size_sqft") or 0))
            except ValueError:
                size_sqft = 0

            try:
                size_marla = float(row.get("size_marla") or 0)
            except ValueError:
                size_marla = 0.0

            property_item = {
                "property_id": row.get("property_id", ""),
                "name": row.get("name", ""),
                "developer": row.get("developer", ""),
                "city": row.get("city", ""),
                "area": row.get("area", ""),
                "type": row.get("type", ""),
                "bedrooms": beds,
                "size_sqft": size_sqft,
                "size_marla": size_marla,
                "price": price,
                "status": row.get("status", "Available"),
                "purpose": row.get("purpose", "Family"),
            }
            items.append(property_item)
    logger.info(f"Loaded {len(items)} properties from catalog")
    return items


PROPERTY_CATALOG = _load_catalog()


def _parse_budget(budget_str: Any) -> tuple[int, int]:
    """Parse a free-text budget string into (min, max) in PKR.

    Supports formats like:
      - "5 crore" / "5cr" / "50000000" / "50 lakh"
      - "50-80 lakh" / "between 5 and 10 crore"
    """
    if not budget_str:
        return (0, float("inf"))
    text = str(budget_str).lower().replace(",", "")
    import re

    # Convert crore/lakh to absolute numbers
    # Pattern: number followed by crore/cr or lakh/lac/l
    numbers = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(crore|cr|lakh|lac|l|million|m)\b", text):
        n = float(m.group(1))
        unit = m.group(2)
        if unit.startswith("cr"):  # crore
            n *= 10_000_000
        elif unit.startswith("m"):  # million
            n *= 1_000_000
        else:  # lakh / lac / l
            n *= 100_000
        numbers.append(int(n))

    # Also pick up raw integer / crore-less numbers
    raw_numbers = [int(float(x)) for x in re.findall(r"\b(\d{6,})\b", text)]
    numbers.extend(raw_numbers)

    if not numbers:
        return (0, float("inf"))
    if len(numbers) == 1:
        # Allow 20% headroom
        return (int(numbers[0] * 0.8), int(numbers[0] * 1.2))

    return (min(numbers), max(numbers))


def match_properties(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return up to 3 properties matching the customer profile.

    Profile keys considered (all optional):
        city, area, property_type, purpose, budget

    Matching strategy (most → least restrictive):
      1. Strict: all non-empty profile fields must match.
      2. Relaxed-area: partial / substring area match (e.g. "DHA" → "DHA Phase 6").
      3. City-only: match city + budget if area produced no results.
    """
    if not PROPERTY_CATALOG:
        return []

    budget_min, budget_max = _parse_budget(profile.get("budget"))
    profile_city = str(profile.get("city", "")).lower().strip() if profile.get("city") else ""
    profile_area = str(profile.get("area", "")).lower().strip() if profile.get("area") else ""
    profile_type = str(profile.get("property_type", "")).lower().strip() if profile.get("property_type") else ""
    profile_purpose = str(profile.get("purpose", "")).lower().strip() if profile.get("purpose") else ""

    profile_marla_val = None
    if profile.get("size_marla") is not None:
        try:
            profile_marla_val = float(profile.get("size_marla"))
        except (ValueError, TypeError):
            profile_marla_val = None

    def _score(p: Dict[str, Any], *, fuzzy_area: bool = False, city_only: bool = False) -> int:
        """Return a relevance score (higher = better match). -1 means skip."""
        if p.get("status", "Available").lower() not in ("available", "reserved"):
            return -1

        score = 0
        p_city = p.get("city", "").lower()
        p_area = p.get("area", "").lower()
        p_type = p.get("type", "").lower()
        p_purpose = p.get("purpose", "").lower()
        price = p.get("price", 0)

        # City match
        if profile_city:
            if p_city == profile_city:
                score += 4
            else:
                return -1  # wrong city -> skip

        # Area match (unless city_only is explicitly allowed)
        if profile_area and not city_only:
            if p_area == profile_area:
                score += 8  # exact area is highest signal
            elif profile_area in p_area or p_area in profile_area:
                score += 6  # broad/sub-area match (e.g. "DHA" in "DHA Phase 6")
            elif fuzzy_area:
                area_tokens = set(profile_area.split())
                prop_tokens = set(p_area.split())
                if area_tokens & prop_tokens:
                    score += 3
                else:
                    return -1
            else:
                return -1  # strict mode - area mismatch

        # Property type match
        if profile_type:
            if p_type == profile_type or profile_type in p_type or p_type in profile_type:
                score += 4
            else:
                score -= 1

        # Size (marla) match
        if profile_marla_val is not None:
            p_marla = float(p.get("size_marla", 0) or 0)
            if abs(p_marla - profile_marla_val) < 0.1:
                score += 6
            else:
                score -= 2

        # Purpose match (e.g. "Investment" ↔ "invest", "Family" ↔ "family")
        if profile_purpose:
            if (profile_purpose in p_purpose or p_purpose in profile_purpose or
                ("invest" in profile_purpose and "invest" in p_purpose) or
                ("family" in profile_purpose and "family" in p_purpose)):
                score += 4

        # Budget match
        if price and budget_min > 0:
            if budget_min <= price <= budget_max:
                score += 4
            else:
                score -= 2  # penalize but don't exclude

        return score

    # --- Pass 1: strict / broad substring area matching ---
    scored = [(p, _score(p, fuzzy_area=False, city_only=False)) for p in PROPERTY_CATALOG]
    matches = [(p, s) for p, s in scored if s >= 0]

    # --- Pass 2: token-overlap fuzzy area matching ---
    if not matches and profile_area:
        scored = [(p, _score(p, fuzzy_area=True, city_only=False)) for p in PROPERTY_CATALOG]
        matches = [(p, s) for p, s in scored if s >= 0]

    # --- Pass 3: city-level fallback ---
    if not matches and profile_city:
        scored = [(p, _score(p, fuzzy_area=True, city_only=True)) for p in PROPERTY_CATALOG]
        matches = [(p, s) for p, s in scored if s >= 0]

    # --- Pass 4: fallback to any available properties for the city ---
    if not matches and profile_city:
        for p in PROPERTY_CATALOG:
            if p.get("city", "").lower() == profile_city and p.get("status", "Available").lower() in ("available", "reserved"):
                matches.append((p, 1))

    if not matches:
        return []

    # Sort by score descending, return top 3
    matches.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in matches[:3]]


def search_properties(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compatibility wrapper for legacy calls.
    Delegates to :func:`match_properties`.
    """
    return match_properties(profile)

