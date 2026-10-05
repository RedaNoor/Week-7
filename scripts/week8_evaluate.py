"""Run reproducible Week 8 model comparisons and evaluation metrics.

This is an evaluation artifact, separate from the low-latency API baseline.
It produces JSON and CSV reports under backend/data/week8/evaluation/.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import Lasso, LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.calibration import calibration_curve
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.ml_service import (
    LEAD_CATEGORICAL,
    LEAD_FEATURES,
    LEAD_NUMERIC,
    PROPERTY_CATEGORICAL,
    PROPERTY_FEATURES,
    PROPERTY_NUMERIC,
    _preprocessor,
    load_property_data,
)
from scripts.prepare_week8_data import make_leads

OUTPUT_DIR = ROOT / "backend" / "data" / "week8" / "evaluation"


def property_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    return frame[PROPERTY_FEATURES], np.log1p(frame["price"])


def regression_report(x_train: pd.DataFrame, x_test: pd.DataFrame, y_train: pd.Series, y_test: pd.Series) -> pd.DataFrame:
    models = {
        "median_baseline": DummyRegressor(strategy="median"),
        "linear_regression": LinearRegression(),
        "ridge": Ridge(alpha=10.0),
        "lasso": Lasso(alpha=0.001, max_iter=3000),
        "random_forest": RandomForestRegressor(n_estimators=60, max_depth=18, min_samples_leaf=2, random_state=42, n_jobs=-1),
    }
    rows = []
    for name, estimator in models.items():
        pipeline = Pipeline([("features", _preprocessor(PROPERTY_CATEGORICAL, PROPERTY_NUMERIC)), ("model", estimator)])
        pipeline.fit(x_train, y_train)
        predicted = np.expm1(pipeline.predict(x_test))
        actual = np.expm1(y_test)
        safe_actual = np.maximum(actual, 1.0)
        rows.append({
            "model": name,
            "mae_pkr": round(mean_absolute_error(actual, predicted), 2),
            "rmse_pkr": round(mean_squared_error(actual, predicted) ** 0.5, 2),
            "r2": round(r2_score(actual, predicted), 4),
            "mape_percent": round(float(np.mean(np.abs((actual - predicted) / safe_actual)) * 100), 2),
        })
    return pd.DataFrame(rows).sort_values("mae_pkr")


def classification_report(leads: pd.DataFrame) -> pd.DataFrame:
    train, test = train_test_split(leads, test_size=0.30, random_state=42, stratify=leads["converted"])
    validation, test = train_test_split(test, test_size=0.50, random_state=42, stratify=test["converted"])
    del validation
    models = {
        "logistic_balanced": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42),
        "random_forest_balanced": RandomForestClassifier(n_estimators=80, max_depth=12, class_weight="balanced", random_state=42, n_jobs=-1),
    }
    rows = []
    for name, estimator in models.items():
        pipeline = Pipeline([("features", _preprocessor(LEAD_CATEGORICAL, LEAD_NUMERIC)), ("model", estimator)])
        pipeline.fit(train[LEAD_FEATURES], train["converted"])
        probability = pipeline.predict_proba(test[LEAD_FEATURES])[:, 1]
        predicted = (probability >= 0.5).astype(int)
        top_count = max(1, int(len(test) * 0.2))
        top_indices = np.argsort(probability)[-top_count:]
        calibration_actual, calibration_predicted = calibration_curve(test["converted"], probability, n_bins=10, strategy="quantile")
        matrix = confusion_matrix(test["converted"], predicted).tolist()
        rows.append({
            "model": name,
            "precision": round(precision_score(test["converted"], predicted, zero_division=0), 4),
            "recall": round(recall_score(test["converted"], predicted, zero_division=0), 4),
            "f1": round(f1_score(test["converted"], predicted, zero_division=0), 4),
            "roc_auc": round(roc_auc_score(test["converted"], probability), 4),
            "pr_auc": round(average_precision_score(test["converted"], probability), 4),
            "precision_at_top_20_percent": round(float(test.iloc[top_indices]["converted"].mean()), 4),
            "brier_score": round(brier_score_loss(test["converted"], probability), 4),
            "calibration_bins": len(calibration_actual),
            "confusion_matrix": matrix,
        })
    return pd.DataFrame(rows).sort_values("pr_auc", ascending=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=20000)
    args = parser.parse_args()
    properties = load_property_data().sample(min(args.sample, len(load_property_data())), random_state=42)
    train, remainder = train_test_split(properties, test_size=0.30, random_state=42)
    validation, test = train_test_split(remainder, test_size=0.50, random_state=42)
    del validation
    x_train, y_train = property_features(train)
    x_test, y_test = property_features(test)
    regression = regression_report(x_train, x_test, y_train, y_test)
    leads = make_leads(properties, count=3000)
    classification = classification_report(leads)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    regression.to_csv(OUTPUT_DIR / "regression_comparison.csv", index=False)
    classification.to_csv(OUTPUT_DIR / "classification_comparison.csv", index=False)
    summary: Dict[str, Any] = {"property_rows": len(properties), "split": "70/15/15", "regression": regression.to_dict("records"), "classification": classification.to_dict("records")}
    (OUTPUT_DIR / "evaluation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()