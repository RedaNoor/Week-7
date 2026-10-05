"""Detect simple feature and price drift for the Week 8 property data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.services.ml_service import load_property_data

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "backend" / "data" / "week8" / "monitoring"


def psi(reference: pd.Series, current: pd.Series, buckets: int = 10) -> float:
    edges = np.unique(np.quantile(reference.dropna(), np.linspace(0, 1, buckets + 1)))
    if len(edges) < 3:
        return 0.0
    ref = np.histogram(reference, bins=edges)[0] / max(len(reference), 1)
    cur = np.histogram(current, bins=edges)[0] / max(len(current), 1)
    ref = np.clip(ref, 1e-6, None)
    cur = np.clip(cur, 1e-6, None)
    return float(np.sum((cur - ref) * np.log(cur / ref)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--price-shift", type=float, default=0.15)
    args = parser.parse_args()
    reference = load_property_data().sample(min(30000, len(load_property_data())), random_state=42)
    current = reference.copy()
    current["price"] *= 1 + args.price_shift
    report = {
        "reference_rows": len(reference),
        "current_rows": len(current),
        "price_shift": args.price_shift,
        "psi": {column: round(psi(reference[column], current[column]), 6) for column in ["price", "area_marla", "bedrooms", "bathrooms"]},
        "alert": "retrain" if args.price_shift >= 0.15 else "monitor",
        "thresholds": {"psi_warning": 0.1, "psi_retrain": 0.2, "mape_retrain_percent": 15},
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "drift_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()