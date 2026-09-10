"""
Call history service — tracks appointment times discussed on prior calls
so that confirmation emails can include a "you discussed X time on call Y"
section.

Storage:
- PostgreSQL `call_history` table (created on init) — primary store
- Falls back to local JSON file at app/data/call_history.json if Postgres
  is unavailable (development mode)

Schema (Postgres):
    id              UUID PRIMARY KEY
    lead_id         TEXT NOT NULL
    client_phone    TEXT
    client_name     TEXT
    property_id     TEXT
    property_title  TEXT
    call_time       TIMESTAMPTZ NOT NULL DEFAULT NOW()
    discussed_time  TEXT          -- the date/time the customer discussed
    call_summary    TEXT          -- 1-line summary of the call
    status          TEXT          -- 'discussed' | 'confirmed' | 'cancelled'
    transcript      TEXT          -- optional full transcript
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger("call_history")
logger.setLevel(logging.INFO)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
FALLBACK_FILE = DATA_DIR / "call_history.json"

try:
    import psycopg2  # type: ignore
    from psycopg2.extras import RealDictCursor  # type: ignore
except ImportError:
    psycopg2 = None  # type: ignore
    RealDictCursor = None  # type: ignore

from app.config import settings


class CallHistoryStore:
    """Persists and retrieves call history records."""

    def __init__(self) -> None:
        self.use_postgres = bool(settings.database_url) and psycopg2 is not None
        if self.use_postgres:
            self._init_table()

    def _connect(self):
        if not self.use_postgres:
            return None
        try:
            return psycopg2.connect(settings.database_url)
        except Exception:
            self.use_postgres = False
            return None

    def _init_table(self) -> None:
        conn = self._connect()
        if conn is None:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS call_history (
                        id              TEXT PRIMARY KEY,
                        lead_id         TEXT NOT NULL,
                        client_phone    TEXT,
                        client_name     TEXT,
                        property_id     TEXT,
                        property_title  TEXT,
                        call_time       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        discussed_time  TEXT,
                        call_summary    TEXT,
                        status          TEXT DEFAULT 'discussed',
                        transcript      TEXT,
                        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_call_history_lead ON call_history(lead_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_call_history_phone ON call_history(client_phone)"
                )
            conn.commit()
        except Exception as e:
            logger.warning(f"[call_history] could not init table: {e}")
            self.use_postgres = False
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def record_call(
        self,
        lead_id: str,
        client_phone: Optional[str] = None,
        client_name: Optional[str] = None,
        property_id: Optional[str] = None,
        property_title: Optional[str] = None,
        discussed_time: Optional[str] = None,
        call_summary: Optional[str] = None,
        status: str = "discussed",
        transcript: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a call where an appointment time was discussed."""
        record_id = f"call_{uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        record = {
            "id": record_id,
            "lead_id": lead_id,
            "client_phone": client_phone,
            "client_name": client_name,
            "property_id": property_id,
            "property_title": property_title,
            "call_time": now_iso,
            "discussed_time": discussed_time,
            "call_summary": (call_summary or "")[:500],
            "status": status,
            "transcript": (transcript or "")[:10000] if transcript else None,
        }

        # Try Postgres first
        if self.use_postgres:
            conn = self._connect()
            if conn is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO call_history
                                (id, lead_id, client_phone, client_name, property_id,
                                 property_title, discussed_time, call_summary, status, transcript)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                record["id"],
                                record["lead_id"],
                                record["client_phone"],
                                record["client_name"],
                                record["property_id"],
                                record["property_title"],
                                record["discussed_time"],
                                record["call_summary"],
                                record["status"],
                                record["transcript"],
                            ),
                        )
                    conn.commit()
                    return record
                except Exception as e:
                    logger.warning(f"[call_history] Postgres insert failed: {e}")
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass

        # Fallback: local JSON file
        history = self._load_fallback()
        history.append(record)
        self._save_fallback(history)
        return record

    def get_history_for_lead(self, lead_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Return call history for a given lead, newest last."""
        if self.use_postgres:
            conn = self._connect()
            if conn is not None:
                try:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            """
                            SELECT id, lead_id, client_phone, client_name, property_id,
                                   property_title, call_time, discussed_time, call_summary, status
                            FROM call_history
                            WHERE lead_id = %s
                            ORDER BY call_time ASC
                            LIMIT %s
                            """,
                            (lead_id, limit),
                        )
                        rows = cur.fetchall()
                    return [dict(r) for r in rows]
                except Exception as e:
                    logger.warning(f"[call_history] Postgres read failed: {e}")
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass

        # Fallback: filter JSON
        history = self._load_fallback()
        return [r for r in history if r.get("lead_id") == lead_id][-limit:]

    def get_history_for_phone(self, phone: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Return call history for a phone number (cross-lead)."""
        if not phone:
            return []
        if self.use_postgres:
            conn = self._connect()
            if conn is not None:
                try:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            """
                            SELECT id, lead_id, client_phone, client_name, property_id,
                                   property_title, call_time, discussed_time, call_summary, status
                            FROM call_history
                            WHERE client_phone = %s
                            ORDER BY call_time ASC
                            LIMIT %s
                            """,
                            (phone, limit),
                        )
                        rows = cur.fetchall()
                    return [dict(r) for r in rows]
                except Exception as e:
                    logger.warning(f"[call_history] Postgres read failed: {e}")
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass

        history = self._load_fallback()
        return [r for r in history if r.get("client_phone") == phone][-limit:]

    def _load_fallback(self) -> List[Dict[str, Any]]:
        if not FALLBACK_FILE.exists():
            return []
        try:
            return json.loads(FALLBACK_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_fallback(self, history: List[Dict[str, Any]]) -> None:
        try:
            FALLBACK_FILE.write_text(
                json.dumps(history, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"[call_history] could not save fallback file: {e}")


call_history_store = CallHistoryStore()


def record_call(phone_number: str, caller_name: str, call_type: str, transcript: str, notes: str, sentiment: str, owner_email: str) -> dict:
    """Compatibility wrapper used by older code (e.g., vapi_service).
    Maps the legacy signature to the current CallHistoryStore.record_call.
    """
    return call_history_store.record_call(
        lead_id=phone_number,
        client_phone=phone_number,
        client_name=caller_name,
        property_id=None,
        property_title=None,
        discussed_time=None,
        call_summary=notes,
        status=call_type,
        transcript=transcript,
    )

