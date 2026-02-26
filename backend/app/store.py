from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from typing import Any


SAVE_BUCKETS = {"journal", "definitions", "threads", "drafts", "audit_logs"}


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def _fresh_state(self) -> dict[str, Any]:
        return {
            "conversation_history": [],
            "structured_symptom_list": [],
            "active_agents": [],
            "audit_log": [],
            "saved": {bucket: [] for bucket in SAVE_BUCKETS},
            "updated_at": datetime.now(UTC).isoformat(),
        }

    def _ensure(self, session_id: str) -> dict[str, Any]:
        if session_id not in self._sessions:
            self._sessions[session_id] = self._fresh_state()
        return self._sessions[session_id]

    def get_session(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._ensure(session_id)
            return deepcopy(state)

    def append_history(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            state = self._ensure(session_id)
            state["conversation_history"].append({"role": role, "content": content})
            state["updated_at"] = datetime.now(UTC).isoformat()

    def set_structured_symptom_list(self, session_id: str, symptoms: list[str]) -> None:
        with self._lock:
            state = self._ensure(session_id)
            state["structured_symptom_list"] = symptoms
            state["updated_at"] = datetime.now(UTC).isoformat()

    def set_active_agents(self, session_id: str, agents: list[str]) -> None:
        with self._lock:
            state = self._ensure(session_id)
            state["active_agents"] = agents
            state["updated_at"] = datetime.now(UTC).isoformat()

    def append_audit_log(self, session_id: str, item: dict[str, Any]) -> None:
        with self._lock:
            state = self._ensure(session_id)
            state["audit_log"].append(item)
            state["saved"]["audit_logs"].append(item)
            state["updated_at"] = datetime.now(UTC).isoformat()

    def save(self, session_id: str, bucket: str, item: dict[str, Any]) -> None:
        if bucket not in SAVE_BUCKETS:
            raise ValueError(f"bucket must be one of {sorted(SAVE_BUCKETS)}")
        with self._lock:
            state = self._ensure(session_id)
            state["saved"][bucket].append(item)
            state["updated_at"] = datetime.now(UTC).isoformat()

    def list_saved(self, session_id: str, bucket: str) -> list[dict[str, Any]]:
        if bucket not in SAVE_BUCKETS:
            raise ValueError(f"bucket must be one of {sorted(SAVE_BUCKETS)}")
        with self._lock:
            state = self._ensure(session_id)
            return deepcopy(state["saved"].get(bucket, []))
