"""Regression checks for the uploaded Week 8 property catalog."""

from app.services.property_matcher import PROPERTY_CATALOG


def test_uploaded_catalog_is_active():
    assert len(PROPERTY_CATALOG) >= 5000
    property_item = PROPERTY_CATALOG[0]
    assert property_item["property_id"].isdigit()
    assert property_item["price"] > 0
    assert property_item["city"]
    assert property_item["area"]