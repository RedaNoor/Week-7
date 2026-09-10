from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from app.services.call_intent import detect_intent
from app.services import profile_extraction


class SessionStateManager:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def _empty_profile(self) -> Dict[str, Any]:
        return profile_extraction.empty_profile()

    def _merge_profile(self, current: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        return profile_extraction.merge_profile(deepcopy(current) if current else None, incoming)

    def get_or_create(self, session_id: str) -> Dict[str, Any]:
        sid = str(session_id or "anonymous")
        if sid not in self.sessions:
            self.sessions[sid] = {
                "session_id": sid,
                "transcripts": [],
                "profile": self._empty_profile(),
                "intent_history": [],
            }
        return self.sessions[sid]

    def record_turn(self, session_id: str, transcript: str) -> Dict[str, Any]:
        sid = str(session_id or "anonymous")
        state = self.get_or_create(sid)
        clean = (transcript or "").strip()
        if not clean:
            return state

        state["transcripts"].append(clean)

        profile = profile_extraction.build_profile(clean)
        state["profile"] = self._merge_profile(state.get("profile", {}), profile)

        intent = detect_intent(clean)
        state["intent_history"].append({
            "transcript": clean,
            "intent": intent,
            "timestamp": "now",
        })
        state["latest_intent"] = intent
        return state

    def get_state(self, session_id: str) -> Dict[str, Any]:
        return self.get_or_create(session_id)


session_state = SessionStateManager()
