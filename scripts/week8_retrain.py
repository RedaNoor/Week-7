"""Promote or roll back a serialized Week 8 valuation model bundle."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import joblib

from app.services.ml_service import MODEL_BUNDLE_PATH, MODEL_VERSION, models

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "backend" / "data" / "week8" / "models"
CURRENT = MODEL_BUNDLE_PATH
BACKUP = MODEL_DIR / "model_bundle.rollback.joblib"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if args.rollback:
        if not BACKUP.exists():
            raise SystemExit("No rollback bundle exists")
        shutil.copy2(BACKUP, CURRENT)
        print(f"rolled back {CURRENT}")
        return
    models.ensure_trained()
    if CURRENT.exists():
        shutil.copy2(CURRENT, BACKUP)
    bundle = {
        "price_model": models.price_model,
        "lead_model": models.lead_model,
        "price_log_residual": models.price_log_residual,
        "price_bounds": models.price_bounds,
        "cities": sorted(models.cities),
        "metrics": models.metrics,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    joblib.dump(bundle, CURRENT)
    metadata = {"model_version": MODEL_VERSION, "promoted_at": datetime.now(timezone.utc).isoformat(), "metrics": models.metrics.get("price", {}), "policy": "promote after holdout comparison; rollback with --rollback"}
    (MODEL_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()