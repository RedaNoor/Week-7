import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from uuid import UUID, uuid4

from app.config import settings
from app.services import profile_extraction

try:
    import psycopg2
    from psycopg2.extras import Json
except Exception:  # pragma: no cover
    psycopg2 = None
    Json = None


class LeadMemory:
    def __init__(self, storage_path: str | None = None):
        base_dir = Path(__file__).resolve().parents[1]
        self.storage_path = Path(storage_path) if storage_path else base_dir / "data" / "lead_memory.json"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.use_postgres = bool(settings.database_url) and psycopg2 is not None
        self.memory_store: Dict[str, Dict[str, Any]] = {}
        self.leads: Dict[str, Dict[str, Any]] = {}
        self._init_storage()

    def _connect(self):
        if not self.use_postgres or psycopg2 is None or not settings.database_url:
            return None
        try:
            return psycopg2.connect(settings.database_url)
        except Exception:
            self.use_postgres = False
            return None

    def _init_storage(self):
        if self.use_postgres:
            conn = self._connect()
            if conn is None:
                self.use_postgres = False
            else:
                with conn.cursor() as cur:
                    # Create lead_memory table with full schema
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS lead_memory (
                            lead_id TEXT PRIMARY KEY,
                            profile JSONB DEFAULT '{}'::jsonb,
                            transcript_history JSONB DEFAULT '[]'::jsonb,
                            intent JSONB DEFAULT '{}'::jsonb,
                            budget VARCHAR(100),
                            city VARCHAR(100),
                            area VARCHAR(100),
                            property_type VARCHAR(50),
                            purpose VARCHAR(50),
                            appointment_interest BOOLEAN DEFAULT FALSE,
                            phone_number VARCHAR(30),
                            customer_name VARCHAR(150),
                            updated_at TIMESTAMPTZ DEFAULT NOW()
                        )
                        """
                    )
                    # Create index for faster lookups
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_lead_memory_phone 
                        ON lead_memory(phone_number)
                        """
                    )
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_lead_memory_city 
                        ON lead_memory(city)
                        """
                    )
                conn.commit()
                conn.close()

        self.memory_store = self._load()
        self.leads = self.memory_store

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if self.use_postgres:
            conn = self._connect()
            if conn is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT lead_id, profile, transcript_history, intent, updated_at FROM lead_memory ORDER BY updated_at DESC"
                        )
                        rows = cur.fetchall()
                    data = {}
                    for lead_id, profile, history, intent, updated_at in rows:
                        record = {
                            "lead_id": lead_id,
                            "profile": profile or {},
                            "transcript_history": history or [],
                            "intent": intent or {},
                            "updated_at": updated_at.isoformat() if updated_at else None,
                        }
                        data[lead_id] = record
                    conn.close()
                    return data
                except Exception:
                    pass
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass

        if not self.storage_path.exists():
            return {}
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass
        return {}

    def _save_file(self):
        self.storage_path.write_text(json.dumps(self.memory_store, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_postgres(self, lead_id: str, record: Dict[str, Any]):
        conn = self._connect()
        if conn is None:
            return
        try:
            profile = record.get("profile", {}) or {}
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO lead_memory (
                        lead_id, profile, transcript_history, intent, 
                        budget, city, area, property_type, purpose, 
                        appointment_interest, phone_number, customer_name, 
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (lead_id)
                    DO UPDATE SET
                        profile = EXCLUDED.profile,
                        transcript_history = EXCLUDED.transcript_history,
                        intent = EXCLUDED.intent,
                        budget = EXCLUDED.budget,
                        city = EXCLUDED.city,
                        area = EXCLUDED.area,
                        property_type = EXCLUDED.property_type,
                        purpose = EXCLUDED.purpose,
                        appointment_interest = EXCLUDED.appointment_interest,
                        phone_number = EXCLUDED.phone_number,
                        customer_name = EXCLUDED.customer_name,
                        updated_at = NOW()
                    """,
                    (
                        lead_id,
                        json.dumps(profile),
                        json.dumps(record.get("transcript_history", []) or []),
                        json.dumps(record.get("intent", {}) or {}),
                        profile.get("budget"),
                        profile.get("city"),
                        profile.get("area"),
                        profile.get("property_type"),
                        profile.get("purpose"),
                        profile.get("appointment_interest", False),
                        profile.get("phone_number") or record.get("phone_number"),
                        profile.get("customer_name") or record.get("customer_name"),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def _merge_profile(self, existing: Dict[str, Any], new_profile: Dict[str, Any]) -> Dict[str, Any]:
        return profile_extraction.merge_profile(existing, new_profile)

    def upsert_lead(self, lead_id: str, data: Dict[str, Any]):
        existing = self.memory_store.setdefault(lead_id, {})

        if "transcript" in data and data["transcript"]:
            history = existing.setdefault("transcript_history", [])
            transcript = str(data["transcript"]).strip()
            if transcript and transcript not in history:
                history.append(transcript)

        if "profile" in data and isinstance(data["profile"], dict):
            existing["profile"] = self._merge_profile(existing.get("profile", {}), data["profile"])

        if "intent" in data:
            existing["intent"] = data["intent"]

        existing["lead_id"] = lead_id
        existing["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.memory_store[lead_id] = existing
        self.leads = self.memory_store

        # Sync with Postgres if enabled
        if self.use_postgres:
            self._save_postgres(lead_id, existing)
            # Also sync with main leads table if we have a phone number
            if existing.get("profile", {}).get("phone_number"):
                self._sync_to_leads_table(lead_id, existing)
        else:
            self._save_file()
        return existing

    def _sync_to_leads_table(self, lead_id: str, record: Dict[str, Any]):
        """Sync lead data to the main leads table in Postgres."""
        if not self.use_postgres:
            return
        
        conn = self._connect()
        if conn is None:
            return
        
        try:
            profile = record.get("profile", {}) or {}
            with conn.cursor() as cur:
                # Check if lead exists in leads table
                cur.execute("SELECT id FROM leads WHERE phone_number = %s", (profile.get("phone_number"),))
                existing = cur.fetchone()
                
                if existing:
                    # Update existing lead
                    cur.execute(
                        """
                        UPDATE leads SET
                            customer_name = COALESCE(%s, customer_name),
                            city = COALESCE(%s, city),
                            area = COALESCE(%s, area),
                            budget = COALESCE(%s, budget),
                            property_type = COALESCE(%s, property_type),
                            purpose = COALESCE(%s, purpose),
                            appointment_interest = COALESCE(%s, appointment_interest),
                            updated_at = NOW()
                        WHERE phone_number = %s
                        """,
                        (
                            profile.get("customer_name"),
                            profile.get("city"),
                            profile.get("area"),
                            profile.get("budget"),
                            profile.get("property_type"),
                            profile.get("purpose"),
                            profile.get("appointment_interest"),
                            profile.get("phone_number"),
                        ),
                    )
                else:
                    # Create new lead
                    lead_uuid = str(uuid4())
                    cur.execute(
                        """
                        INSERT INTO leads (
                            id, phone_number, customer_name, city, area, 
                            budget, property_type, purpose, appointment_interest
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            lead_uuid,
                            profile.get("phone_number"),
                            profile.get("customer_name"),
                            profile.get("city"),
                            profile.get("area"),
                            profile.get("budget"),
                            profile.get("property_type"),
                            profile.get("purpose"),
                            profile.get("appointment_interest", False),
                        ),
                    )
            conn.commit()
        except Exception as e:
            print(f"Error syncing to leads table: {e}")
        finally:
            conn.close()

    def get_lead(self, lead_id: str):
        return self.memory_store.get(lead_id, {})

    def extract_preferences(self, transcript: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        lower = (transcript or "").lower()

        if "budget" in lower or "crore" in lower:
            result["budget_discussed"] = True
        if any(word in lower for word in ["dha", "gulshan", "bahria", "canal", "g-11", "f-11", "clifton"]):
            result["city_or_area_discussed"] = True
        if "buy" in lower or "purchase" in lower:
            result["purpose"] = "buy"
        elif "rent" in lower:
            result["purpose"] = "rent"
        elif "invest" in lower or "investment" in lower:
            result["purpose"] = "invest"
        return result

    def build_profile(self, raw_transcript: str) -> Dict[str, Any]:
        return profile_extraction.build_profile(raw_transcript)


lead_memory = LeadMemory()


def extract_profile(phone_number: str, conversation_text: str) -> None:
    """Compatibility wrapper used by Vapi service.
    Builds a lead profile from the conversation transcript and stores/updates it.
    The `phone_number` is used as the lead identifier.
    """
    profile = lead_memory.build_profile(conversation_text)
    # Store both the raw transcript and the extracted profile.
    lead_memory.upsert_lead(phone_number, {"profile": profile, "transcript": conversation_text})

