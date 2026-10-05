"""Focused smoke tests for the Week 8 model contract."""

from app.services.ml_service import models


def test_week8_models_score_and_predict():
    price = models.predict_price({
        "city": "Islamabad", "location": "G-10", "property_type": "Flat",
        "area_marla": 4, "bedrooms": 2, "bathrooms": 2,
    })
    assert price["lower_price_pkr"] < price["predicted_price_pkr"] < price["upper_price_pkr"]
    lead = models.score_lead({
        "source": "call", "budget_pkr": 10000000, "preferred_city": "Islamabad",
        "purpose": "buy", "number_of_calls": 2, "call_duration_seconds": 200,
        "response_time_minutes": 30, "visit_booked": 1,
        "days_since_first_contact": 2, "objection_raised": "none",
    })
    assert lead["segment"] in {"Hot", "Warm", "Cold"}