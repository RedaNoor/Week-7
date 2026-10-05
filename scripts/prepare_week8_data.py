"""Prepare the Week 8 datasets without modifying the downloaded source CSV.

Usage from the repository root:
    python scripts/prepare_week8_data.py

The amenity and distance fields are deterministic, documented assumptions for
areas in Pakistan. They are useful for a reproducible capstone baseline, but
must be replaced by verified GIS or listing data before commercial use.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dataset_properties.csv"
OUTPUT = ROOT / "backend" / "data" / "week8"

AREA_PROFILE = {
    "dha": ("premium", "gated community|parks|commercial area|security|schools", 1.2, 2.0, 2.5),
    "bahria": ("premium", "gated community|parks|mosque|commercial area|security", 1.5, 2.5, 3.0),
    "gulberg": ("premium", "commercial area|parks|schools|hospitals|public transport", 0.8, 1.5, 2.0),
    "f-6": ("premium", "parks|schools|hospitals|commercial area|security", 0.7, 1.0, 1.5),
    "f-7": ("premium", "parks|schools|hospitals|commercial area|security", 0.9, 1.2, 1.8),
    "e-11": ("mid", "mosque|commercial area|schools|public transport", 1.4, 2.0, 2.8),
    "g-11": ("mid", "parks|schools|mosque|commercial area", 1.5, 2.2, 3.0),
}


def profile_for(location: str) -> tuple[str, str, float, float, float]:
    lowered = location.lower()
    for token, profile in AREA_PROFILE.items():
        if token in lowered:
            return profile
    return "budget", "mosque|local market|public transport", 2.5, 4.0, 5.0


def prepare_properties(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["area_marla"] = pd.to_numeric(result["Area Size"], errors="coerce")
    result.loc[result["Area Type"].str.contains("Kanal", case=False, na=False), "area_marla"] *= 20
    result.loc[result["Area Type"].str.contains("sq", case=False, na=False), "area_marla"] /= 272.25
    profiles = result["location"].map(profile_for)
    result[["society_tier", "amenities", "distance_main_road_km", "distance_school_km", "distance_hospital_km"]] = pd.DataFrame(profiles.tolist(), index=result.index)
    result["amenity_score"] = result["amenities"].str.count(r"\|") + 1
    result["property_age_years"] = 2026 - pd.to_datetime(result["date_added"], errors="coerce").dt.year.fillna(2019)
    result["floors"] = np.where(result["property_type"].isin(["Flat", "Penthouse"]), 1, 2)
    result["corner"] = result["page_url"].str.contains("corner", case=False, na=False).astype(int)
    result["park_facing"] = result["page_url"].str.contains("park|green", case=False, na=False).astype(int)
    return result


def make_leads(properties: pd.DataFrame, count: int = 3000) -> pd.DataFrame:
    rng = random.Random(42)
    cities = sorted(properties["city"].dropna().unique())
    rows = []
    for lead_id in range(1, count + 1):
        calls = rng.randint(0, 8)
        visit = int(rng.random() < min(0.7, 0.05 + calls * 0.08))
        duration = rng.randint(20, 900)
        response = rng.randint(1, 1440)
        converted = int(-2.5 + calls * 0.35 + visit * 1.5 + duration / 900 - response / 1500 + rng.random() > 0.2)
        rows.append({
            "lead_id": f"L{lead_id:05d}", "source": rng.choice(["call", "WhatsApp", "Facebook", "website"]),
            "budget_pkr": rng.randint(30, 300) * 100000, "preferred_city": rng.choice(cities),
            "purpose": rng.choice(["buy", "rent", "invest"]), "number_of_calls": calls,
            "call_duration_seconds": duration, "response_time_minutes": response,
            "visit_booked": visit, "days_since_first_contact": rng.randint(0, 60),
            "objection_raised": rng.choice(["none", "price", "location", "financing"]), "converted": converted,
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--leads", type=int, default=3000)
    args = parser.parse_args()
    properties = prepare_properties(pd.read_csv(SOURCE))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    properties.to_csv(OUTPUT / "properties_enriched.csv", index=False)
    make_leads(properties, args.leads).to_csv(OUTPUT / "leads.csv", index=False)
    print(f"wrote {len(properties)} enriched properties and {args.leads} leads to {OUTPUT}")


if __name__ == "__main__":
    main()