"""
Property catalog loader and matcher.

Loads the property catalog from the uploaded `dataset_properties.csv` when it
is available and exposes:
- PROPERTY_CATALOG: the full list (loaded at import time)
- match_properties(profile): returns up to 3 properties matching the
  customer's stated budget / city / area / property type / purpose

The normalized catalog shape is:
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
WORKSPACE_ROOT = ROOT.parent
PROPERTY_CATALOG: List[Dict[str, Any]] = []


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value or "").replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value or "").replace(",", "").strip()))
    except (TypeError, ValueError):
        return default


def _normalize_row(row: Dict[str, str], *, raw_dataset: bool) -> Dict[str, Any]:
    if raw_dataset:
        area_marla = _as_float(row.get("Area Size"))
        area_type = (row.get("Area Type") or "Marla").lower()
        if "kanal" in area_type:
            area_marla *= 20
        elif "sq" in area_type or "feet" in area_type:
            area_marla /= 272.25
        property_type = row.get("property_type") or "Unknown"
        location = row.get("location") or "Unknown"
        city = row.get("city") or "Unknown"
        return {
            "property_id": row.get("property_id", ""),
            "name": f"{property_type} in {location}, {city}",
            "developer": row.get("agency") or "Independent Listing",
            "city": city,
            "area": location,
            "type": property_type,
            "bedrooms": _as_int(row.get("bedrooms")),
            "bathrooms": _as_int(row.get("baths")),
            "size_sqft": round(area_marla * 272.25),
            "size_marla": area_marla,
            "price": _as_int(row.get("price")),
            "status": "Available",
            "purpose": row.get("purpose") or "For Sale",
            "province_name": row.get("province_name") or "",
            "latitude": _as_float(row.get("latitude")),
            "longitude": _as_float(row.get("longitude")),
            "source_url": row.get("page_url") or "",
        }

    return {
        "property_id": row.get("property_id", ""),
        "name": row.get("name", ""),
        "developer": row.get("developer", ""),
        "city": row.get("city", ""),
        "area": row.get("area", ""),
        "type": row.get("type", ""),
        "bedrooms": _as_int(row.get("bedrooms")),
        "bathrooms": _as_int(row.get("bathrooms")),
        "size_sqft": _as_int(row.get("size_sqft")),
        "size_marla": _as_float(row.get("size_marla")),
        "price": _as_int(row.get("price")),
        "status": row.get("status", "Available"),
        "purpose": row.get("purpose", "Family"),
    }


def _load_catalog() -> List[Dict[str, Any]]:
    candidate_datasets = [
        WORKSPACE_ROOT / "dataset_properties.csv",
        ROOT / "dataset_properties.csv",
        Path.cwd() / "dataset_properties.csv",
        ROOT / "data" / "dataset_properties.csv",
        Path(__file__).resolve().parents[3] / "dataset_properties.csv",
    ]
    
    catalog_path = None
    raw_dataset = False
    for candidate in candidate_datasets:
        if candidate.exists():
            catalog_path = candidate
            raw_dataset = True
            break
            
    if not catalog_path:
        fallback_candidates = [
            ROOT / "data" / "properties.csv",
            WORKSPACE_ROOT / "backend" / "data" / "properties.csv",
            Path.cwd() / "backend" / "data" / "properties.csv",
        ]
        for fallback in fallback_candidates:
            if fallback.exists():
                catalog_path = fallback
                raw_dataset = False
                break

    if not catalog_path or not catalog_path.exists():
        logger.warning("Property dataset not found at any candidate path")
        return []

    items: List[Dict[str, Any]] = []
    with catalog_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            property_item = _normalize_row(row, raw_dataset=raw_dataset)
            if property_item["property_id"] and property_item["price"] > 0:
                items.append(property_item)
    logger.info("Loaded %s properties from %s", len(items), catalog_path.name)
    return items


PROPERTY_CATALOG = _load_catalog()


def _parse_budget(budget_str: Any) -> tuple[int, int]:
    """Parse a free-text budget string into (min, max) in PKR."""
    if not budget_str:
        return (0, float("inf"))
    text = str(budget_str).lower().replace(",", "")
    import re

    numbers = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(crores?|cr|karor|kror|lakhs?|lacs?|lk|million|m)\b", text):
        n = float(m.group(1))
        unit = m.group(2)
        if unit.startswith("cr") or "kror" in unit or "karor" in unit:  # crore
            n *= 10_000_000
        elif unit.startswith("m") and not unit.startswith("mar"):  # million
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
        # User specified an upper bound / target budget (allow 10% headroom)
        return (0, int(numbers[0] * 1.10))

    return (min(numbers), int(max(numbers) * 1.05))


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
        if price and budget_max > 0 and budget_max != float("inf"):
            if price <= budget_max:
                score += 8  # Strong reward for within budget
            else:
                score -= 12  # Strong penalty for exceeding budget

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

