from pathlib import Path


def test_leads_schema_includes_profile_data():
    schema_sql = Path("database_schema.sql").read_text(encoding="utf-8")
    assert "profile_data" in schema_sql
