"""
Generate property brochure text files for every property in the catalog.

Each brochure is a short marketing-style document with the property's
details: location, developer, size, price, payment plans, and the
amenities / nearby facilities. The text is read from the CSV files
in /home/z/my-project/backend/data/.
"""

from __future__ import annotations

import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "backend" / "data"
BROCHURE_DIR = Path(__file__).resolve().parent.parent / "backend" / "documents" / "property_brochures"
BROCHURE_DIR.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def format_price(price: int) -> str:
    if price >= 10_000_000:
        return f"PKR {price / 10_000_000:.2f} crore"
    if price >= 100_000:
        return f"PKR {price / 100_000:.1f} lakh"
    return f"PKR {price:,}"


def format_size(sqft: int, marla: float) -> str:
    if marla >= 20:
        return f"{marla / 20:.1f} kanal ({sqft:,} sqft)"
    return f"{marla} marla ({sqft:,} sqft)"


def build_brochure(prop: dict, amenities: list[str],
                   plans: list[dict], hospitals: list[dict],
                   schools: list[dict]) -> str:
    lines = []
    pid = prop["property_id"]
    lines.append(f"PROPERTY BROCHURE — {pid}")
    lines.append("=" * 60)
    lines.append("")
    lines.append(prop["name"])
    lines.append("")
    lines.append("-" * 60)
    lines.append("OVERVIEW")
    lines.append("-" * 60)
    lines.append(f"Developer    : {prop['developer']}")
    lines.append(f"City         : {prop['city']}")
    lines.append(f"Location     : {prop['area']}")
    lines.append(f"Property Type: {prop['type']}")
    if int(prop.get("bedrooms", 0)) > 0:
        lines.append(f"Bedrooms     : {prop['bedrooms']}")
    lines.append(f"Size         : {format_size(int(prop['size_sqft']), float(prop['size_marla']))}")
    lines.append(f"Price        : {format_price(int(prop['price']))}")
    lines.append(f"Status       : {prop['status']}")
    lines.append(f"Purpose      : {prop['purpose']}")
    lines.append("")

    if amenities:
        lines.append("-" * 60)
        lines.append("AMENITIES")
        lines.append("-" * 60)
        for a in amenities:
            lines.append(f"  • {a}")
        lines.append("")

    if plans:
        lines.append("-" * 60)
        lines.append("PAYMENT PLANS")
        lines.append("-" * 60)
        for plan in plans:
            lines.append(f"  • {plan['plan_name']}")
            lines.append(f"      Down payment: {plan['down_payment_percent']}%")
            lines.append(f"      Installments: {plan['installment_months']} months")
            lines.append(f"      Total payable: {format_price(int(plan['total_payable']))}")
            lines.append(f"      Note: {plan['description']}")
            lines.append("")

    # Find nearby hospitals and schools for this city
    city = prop["city"]
    nearby_hospitals = [h for h in hospitals if h["city"] == city][:4]
    nearby_schools = [s for s in schools if s["city"] == city][:4]
    if nearby_hospitals:
        lines.append("-" * 60)
        lines.append("NEARBY HOSPITALS")
        lines.append("-" * 60)
        for h in nearby_hospitals:
            lines.append(f"  • {h['name']} (near {h['near_location']})")
        lines.append("")
    if nearby_schools:
        lines.append("-" * 60)
        lines.append("NEARBY SCHOOLS")
        lines.append("-" * 60)
        for s in nearby_schools:
            lines.append(f"  • {s['name']} (near {s['near_location']}) — {s['type']}")
        lines.append("")

    lines.append("-" * 60)
    lines.append("CONTACT")
    lines.append("-" * 60)
    lines.append("To schedule a visit, contact our sales team:")
    lines.append("  Phone: +92 21 111 222 333")
    lines.append("  Email: sales@realestatehub.pk")
    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def main() -> None:
    properties = load_csv(DATA_DIR / "properties.csv")
    amenities_rows = load_csv(DATA_DIR / "amenities.csv")
    plans_rows = load_csv(DATA_DIR / "payment_plans.csv")
    hospitals = load_csv(DATA_DIR / "hospitals.csv")
    schools = load_csv(DATA_DIR / "schools.csv")

    print(f"Loaded {len(properties)} properties")
    print(f"Writing brochures to {BROCHURE_DIR}")

    for prop in properties:
        pid = prop["property_id"]
        amenities = [a["amenity"] for a in amenities_rows if a["property_id"] == pid]
        plans = [p for p in plans_rows if p["property_id"] == pid]
        brochure = build_brochure(prop, amenities, plans, hospitals, schools)
        out = BROCHURE_DIR / f"{pid}.txt"
        out.write_text(brochure, encoding="utf-8")

    print(f"Wrote {len(properties)} brochures")


if __name__ == "__main__":
    main()
