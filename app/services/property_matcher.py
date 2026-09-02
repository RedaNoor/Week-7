import csv
from pathlib import Path
from typing import List, Dict, Any


# parents[0] = app/services, parents[1] = app, parents[2] = project root.
# The property catalog lives in the project-level data/ folder (shared with
# the knowledge base scripts), not inside app/.
ROOT = Path(__file__).resolve().parents[2]
PROPERTY_CATALOG: List[Dict[str, Any]] = []


def _load_catalog() -> List[Dict[str, Any]]:
    catalog_path = ROOT / "data" / "properties.csv"
    if not catalog_path.exists():
        print(f"[property_matcher] properties.csv not found at {catalog_path}")
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

            property_item = {
                "property_id": row.get("property_id", ""),
                "name": row.get("name", ""),
                "developer": row.get("developer", ""),
                "city": row.get("city", ""),
                "area": row.get("area", ""),
                "type": row.get("type", ""),
                "bedrooms": int(row.get("bedrooms") or 0),
                "price": price,
                "status": row.get("status", "Available"),
                "purpose": row.get("purpose", "Family"),
            }
            items.append(property_item)
    return items


PROPERTY_CATALOG = _load_catalog()


def match_properties(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not PROPERTY_CATALOG:
        return []

    matches: List[Dict[str, Any]] = []
    for property_item in PROPERTY_CATALOG:
        city_match = True
        area_match = True
        purpose_match = True
        type_match = True
        status_match = property_item.get("status", "Available").lower() == "available"

        if profile.get("city") and property_item.get("city", "").lower() != str(profile["city"]).lower():
            city_match = False
        if profile.get("area") and str(profile["area"]).lower() not in str(property_item.get("area", "")).lower():
            area_match = False
        if profile.get("purpose") and str(property_item.get("purpose", "")).lower() != str(profile["purpose"]).lower():
            purpose_match = False
        if profile.get("property_type") and str(property_item.get("type", "")).lower() != str(profile["property_type"]).lower():
            type_match = False

        if city_match and area_match and purpose_match and type_match and status_match:
            matches.append(property_item)

    if not matches:
        return PROPERTY_CATALOG[:3]

    return matches[:3]
