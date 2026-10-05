"""Week 8 valuation and lead-scoring models.

The raw Zameen listing export is kept immutable. This service derives the
features needed by the Week 8 models and trains lazily on first use so the
Week 7 API can still start without doing ML work.
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import mean_absolute_error, r2_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from app.config import settings

logger = logging.getLogger("ml_service")
ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = ROOT / "dataset_properties.csv"
LOG_PATH = ROOT / "backend" / "data" / "ml_prediction_log.jsonl"
MODEL_VERSION = "week8-v1"
MODEL_BUNDLE_PATH = ROOT / settings.ml_model_bundle_path

PROPERTY_FEATURES = [
    "city", "location", "property_type", "province_name", "purpose",
    "area_type", "area_marla", "bathrooms", "bedrooms", "latitude",
    "longitude", "amenity_score", "listing_year",
]
PROPERTY_CATEGORICAL = ["city", "location", "property_type", "province_name", "purpose", "area_type"]
PROPERTY_NUMERIC = [item for item in PROPERTY_FEATURES if item not in PROPERTY_CATEGORICAL]
LEAD_FEATURES = [
    "source", "budget_pkr", "preferred_city", "purpose", "number_of_calls",
    "call_duration_seconds", "response_time_minutes", "visit_booked",
    "days_since_first_contact", "objection_raised",
]
LEAD_CATEGORICAL = ["source", "preferred_city", "purpose", "objection_raised"]
LEAD_NUMERIC = [item for item in LEAD_FEATURES if item not in LEAD_CATEGORICAL]


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(str(value).replace(",", "").strip())
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _area_marla(area_type: Any, area_size: Any) -> float:
    size = _number(area_size)
    kind = str(area_type or "").lower().replace(" ", "")
    if "kanal" in kind:
        return size * 20
    if "sq" in kind or "feet" in kind:
        return size / 272.25
    return size


def _amenity_score(row: pd.Series) -> float:
    """Deterministic proxy for missing amenities, documented as an assumption."""
    premium_areas = {"dha", "bahria", "gulberg", "f-6", "f-7", "e-11", "g-11"}
    location = str(row.get("location", "")).lower()
    score = 2.0
    if any(area in location for area in premium_areas):
        score += 2.0
    if str(row.get("property_type", "")).lower() in {"house", "farm house", "penthouse"}:
        score += 1.0
    return min(score, 5.0)


def load_property_data() -> pd.DataFrame:
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(f"Week 8 property dataset not found: {SOURCE_PATH}")
    frame = pd.read_csv(SOURCE_PATH)
    frame = frame.rename(columns={"baths": "bathrooms"})
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame["area_marla"] = [_area_marla(kind, size) for kind, size in zip(frame["Area Type"], frame["Area Size"])]
    frame["bathrooms"] = pd.to_numeric(frame["bathrooms"], errors="coerce").fillna(0)
    frame["bedrooms"] = pd.to_numeric(frame["bedrooms"], errors="coerce").fillna(0)
    frame["listing_year"] = pd.to_datetime(frame["date_added"], errors="coerce").dt.year.fillna(2019).astype(float)
    frame["amenity_score"] = frame.apply(_amenity_score, axis=1)
    frame["purpose"] = frame["purpose"].fillna("For Sale")
    frame["area_type"] = frame["Area Type"].fillna("Marla")
    for column in ("location", "city", "property_type", "province_name"):
        frame[column] = frame[column].fillna("Unknown")
    frame["latitude"] = pd.to_numeric(frame["latitude"], errors="coerce").fillna(frame["latitude"].median())
    frame["longitude"] = pd.to_numeric(frame["longitude"], errors="coerce").fillna(frame["longitude"].median())
    return frame[frame["price"] > 0].copy()


def _preprocessor(categorical: List[str], numeric: List[str]) -> ColumnTransformer:
    return ColumnTransformer([
        ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
        ("numeric", StandardScaler(), numeric),
    ])


class Week8Models:
    def __init__(self) -> None:
        self._lock = Lock()
        self.price_model: Pipeline | None = None
        self.lead_model: Pipeline | None = None
        self.price_log_residual = 0.0
        self.price_bounds: Dict[str, tuple[float, float]] = {}
        self.metrics: Dict[str, Any] = {}
        self.cities: set[str] = set()
        self.artifact_loaded = False
        self.trained_at = ""

    def ensure_trained(self) -> None:
        if self.price_model is not None:
            return
        with self._lock:
            if self.price_model is not None:
                return
            if self._load_bundle():
                return
            if settings.ml_require_artifact or settings.app_env.lower() == "production":
                raise RuntimeError(f"ML model bundle is required but unavailable at {MODEL_BUNDLE_PATH}")
            properties = load_property_data()
            self.cities = {str(value).lower() for value in properties["city"].unique()}
            sample = properties.sample(min(len(properties), 30000), random_state=42)
            train, test = train_test_split(sample, test_size=0.2, random_state=42)
            self.price_model = Pipeline([
                ("features", _preprocessor(PROPERTY_CATEGORICAL, PROPERTY_NUMERIC)),
                ("model", RandomForestRegressor(n_estimators=80, max_depth=18, min_samples_leaf=2, random_state=42, n_jobs=-1)),
            ])
            self.price_model.fit(train[PROPERTY_FEATURES], np.log1p(train["price"]))
            predicted_log = self.price_model.predict(test[PROPERTY_FEATURES])
            predicted = np.expm1(predicted_log)
            self.price_log_residual = float(np.std(np.log1p(test["price"].to_numpy()) - predicted_log))
            self.metrics["price"] = {"mae_pkr": round(mean_absolute_error(test["price"], predicted), 2), "r2": round(r2_score(test["price"], predicted), 4)}
            for column in ("area_marla", "bedrooms", "bathrooms"):
                self.price_bounds[column] = (float(properties[column].quantile(0.01)), float(properties[column].quantile(0.99)))
            self.lead_model = self._train_leads()
            self.trained_at = datetime.now(timezone.utc).isoformat()
            logger.info("Week 8 models trained: %s", self.metrics)

    def _load_bundle(self) -> bool:
        if not MODEL_BUNDLE_PATH.exists():
            return False
        try:
            bundle = joblib.load(MODEL_BUNDLE_PATH)
            if not isinstance(bundle, dict) or not bundle.get("price_model") or not bundle.get("lead_model"):
                raise ValueError("bundle must contain price_model and lead_model")
            self.price_model = bundle["price_model"]
            self.lead_model = bundle["lead_model"]
            self.price_log_residual = float(bundle["price_log_residual"])
            self.price_bounds = bundle["price_bounds"]
            self.metrics = bundle.get("metrics", {})
            self.cities = set(bundle["cities"])
            self.trained_at = str(bundle.get("trained_at", "artifact"))
            self.artifact_loaded = True
            logger.info("Loaded Week 8 model bundle from %s", MODEL_BUNDLE_PATH)
            return True
        except Exception as error:
            logger.warning("Could not load ML model bundle: %s", error)
            if settings.ml_require_artifact or settings.app_env.lower() == "production":
                raise RuntimeError(f"Invalid ML model bundle at {MODEL_BUNDLE_PATH}: {error}") from error
            return False

    def _train_leads(self) -> Pipeline:
        rng = random.Random(42)
        cities = sorted(self.cities) or ["lahore"]
        rows = []
        for _ in range(4000):
            calls = rng.randint(0, 8)
            visit = rng.random() < min(0.7, 0.05 + calls * 0.08)
            row = {
                "source": rng.choice(["call", "WhatsApp", "Facebook", "website"]),
                "budget_pkr": rng.randint(30, 300) * 100000,
                "preferred_city": rng.choice(cities),
                "purpose": rng.choice(["buy", "rent", "invest"]),
                "number_of_calls": calls,
                "call_duration_seconds": rng.randint(20, 900),
                "response_time_minutes": rng.randint(1, 1440),
                "visit_booked": int(visit),
                "days_since_first_contact": rng.randint(0, 60),
                "objection_raised": rng.choice(["none", "price", "location", "financing"]),
            }
            score = -2.5 + calls * 0.35 + int(visit) * 1.5 + row["call_duration_seconds"] / 900 - row["response_time_minutes"] / 1500
            row["converted"] = int(score + rng.random() > 0.2)
            rows.append(row)
        data = pd.DataFrame(rows)
        train, test = train_test_split(data, test_size=0.2, random_state=42, stratify=data["converted"])
        model = Pipeline([
            ("features", _preprocessor(LEAD_CATEGORICAL, LEAD_NUMERIC)),
            ("model", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
        ])
        model.fit(train[LEAD_FEATURES], train["converted"])
        self.metrics["lead"] = {"roc_auc": round(roc_auc_score(test["converted"], model.predict_proba(test[LEAD_FEATURES])[:, 1]), 4)}
        return model

    def _property_row(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        row = {key: payload.get(key) for key in PROPERTY_FEATURES}
        for key in ("area_marla", "bathrooms", "bedrooms", "latitude", "longitude", "amenity_score", "listing_year"):
            row[key] = _number(payload.get(key), 3.0 if key == "amenity_score" else 2019.0 if key == "listing_year" else 0.0)
        for key in PROPERTY_CATEGORICAL:
            row[key] = str(row.get(key) or "Unknown")
        return row

    def predict_price(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_trained()
        row = self._property_row(payload)
        for key in ("area_marla", "bedrooms", "bathrooms"):
            low, high = self.price_bounds[key]
            if not low <= row[key] <= high:
                raise ValueError(f"{key} is outside the supported training range ({low:.2f} to {high:.2f})")
        if str(row["city"]).lower() not in self.cities:
            raise ValueError(f"Unknown city. Supported cities: {', '.join(sorted(self.cities))}")
        predicted = float(np.expm1(self.price_model.predict(pd.DataFrame([row])[PROPERTY_FEATURES])[0]))
        listed = _number(payload.get("listed_price"))
        low = max(0.0, math.expm1(math.log1p(predicted) - 1.96 * self.price_log_residual))
        high = math.expm1(math.log1p(predicted) + 1.96 * self.price_log_residual)
        verdict = "Fair" if not listed or predicted * 0.9 <= listed <= predicted * 1.1 else "Underpriced" if listed < predicted else "Overpriced"
        result = {"predicted_price_pkr": round(predicted), "lower_price_pkr": round(low), "upper_price_pkr": round(high), "listed_price_pkr": round(listed) if listed else None, "verdict": verdict, "model_version": MODEL_VERSION, "disclaimer": "This is a machine-learning estimate, not an official valuation."}
        self._log("price", payload, result)
        return result

    def score_lead(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_trained()
        row = {key: payload.get(key) for key in LEAD_FEATURES}
        for key in LEAD_NUMERIC:
            row[key] = _number(row[key])
        for key in LEAD_CATEGORICAL:
            row[key] = str(row.get(key) or "unknown")
        probability = float(self.lead_model.predict_proba(pd.DataFrame([row])[LEAD_FEATURES])[0, 1])
        category = "Hot" if probability >= 0.7 else "Warm" if probability >= 0.4 else "Cold"
        result = {"conversion_probability": round(probability, 4), "segment": category, "recommended_response_time": "within 1 hour" if category == "Hot" else "within 24 hours" if category == "Warm" else "follow-up campaign", "model_version": MODEL_VERSION}
        self._log("lead", payload, result)
        return result

    def explain(self, kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = self.predict_price(payload) if kind == "price" else self.score_lead(payload)
        result["explanation"] = (["location and city were compared with learned Pakistani listing patterns", "normalized plot size, bedrooms, and bathrooms were used", "the range reflects historical model error"] if kind == "price" else ["call frequency and duration indicate engagement", "visit-booking status strongly affects conversion likelihood", "response speed and stated budget are included"])
        try:
            import shap

            if kind == "price":
                row = self._property_row(payload)
                transformed = self.price_model.named_steps["features"].transform(pd.DataFrame([row])[PROPERTY_FEATURES])
                values = shap.TreeExplainer(self.price_model.named_steps["model"]).shap_values(transformed)[0]
                names = self.price_model.named_steps["features"].get_feature_names_out()
            else:
                row = {key: payload.get(key) for key in LEAD_FEATURES}
                for key in LEAD_NUMERIC:
                    row[key] = _number(row[key])
                for key in LEAD_CATEGORICAL:
                    row[key] = str(row.get(key) or "unknown")
                transformed = self.lead_model.named_steps["features"].transform(pd.DataFrame([row])[LEAD_FEATURES])
                values = shap.LinearExplainer(self.lead_model.named_steps["model"], transformed).shap_values(transformed)[0]
                names = self.lead_model.named_steps["features"].get_feature_names_out()
            top = np.argsort(np.abs(values))[-5:][::-1]
            result["shap_features"] = [{"feature": str(names[index]), "impact": round(float(values[index]), 5)} for index in top]
            result["explanation_note"] = "Top local SHAP contributions are included; positive values increase the model output."
        except (ImportError, AttributeError, TypeError, ValueError):
            result["explanation_note"] = "Install the pinned SHAP dependency to include local SHAP contributions."
        return result

    def _log(self, kind: str, payload: Dict[str, Any], result: Dict[str, Any]) -> None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "kind": kind, "model_version": MODEL_VERSION, "input": payload, "output": result}
        with LOG_PATH.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, default=str) + "\n")


models = Week8Models()