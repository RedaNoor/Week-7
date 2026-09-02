"""
Thin compatibility wrapper around db_store_enhanced.

This module used to define its own SQLAlchemy models for `leads` and
`call_sessions`, a second, incompatible schema for the same two tables
that db_store_enhanced.py also defines and creates. Two declarative Bases
both calling `create_all()` against the same table names is the kind of
thing that works by accident until it doesn't. This file now keeps the
same function signatures (init_db, save_lead_profile, fetch_lead) so
nothing calling into it needs to change, but there is exactly one schema
underneath: the one in db_store_enhanced.py.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from app.services import db_store_enhanced


def _lead_uuid(lead_id: str) -> uuid.UUID:
    """Deterministically map an arbitrary caller/session ID (which may not
    be a UUID, e.g. a Vapi call ID) to a stable UUID so it can be used as
    a Postgres primary key."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, str(lead_id))


def init_db() -> bool:
    return db_store_enhanced.init_db()


def save_lead_profile(
    lead_id: str,
    profile: Dict[str, Any],
    transcript: str | None = None,
    intent: Dict[str, Any] | None = None,
) -> Optional[Dict[str, Any]]:
    result = db_store_enhanced.LeadStore.create_or_update_lead(
        lead_id=_lead_uuid(lead_id),
        phone_number=profile.get("phone_number"),
        customer_name=profile.get("customer_name"),
        profile=profile,
    )
    if result is None:
        return None
    return {"lead_id": lead_id, "profile": profile, "status": result.get("status")}


def fetch_lead(lead_id: str) -> Optional[Dict[str, Any]]:
    record = db_store_enhanced.LeadStore.fetch_lead(_lead_uuid(lead_id))
    if record is None:
        return None
    record["lead_id"] = lead_id
    return record
