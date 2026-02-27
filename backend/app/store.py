import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


SAVE_BUCKETS = {"journal", "definitions", "threads", "drafts", "audit_logs"}


class SessionStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        default_path = Path(__file__).resolve().parents[1] / "data" / "local.db"
        self._db_path = Path(db_path) if db_path is not None else default_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize_schema()

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_schema(self) -> None:
        with self._lock:
            with self._connection() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        structured_symptom_list TEXT NOT NULL DEFAULT '[]',
                        active_agents TEXT NOT NULL DEFAULT '[]',
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversation_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS saved_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        bucket TEXT NOT NULL,
                        item_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )

    def _ensure_session(self, conn: sqlite3.Connection, session_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        conn.execute(
            """
            INSERT INTO sessions (session_id, structured_symptom_list, active_agents, updated_at)
            VALUES (?, '[]', '[]', ?)
            ON CONFLICT(session_id) DO NOTHING
            """,
            (session_id, now),
        )

    def get_session(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            with self._connection() as conn:
                self._ensure_session(conn, session_id)
                session_row = conn.execute(
                    """
                    SELECT structured_symptom_list, active_agents, updated_at
                    FROM sessions
                    WHERE session_id = ?
                    """,
                    (session_id,),
                ).fetchone()
                history_rows = conn.execute(
                    """
                    SELECT role, content
                    FROM conversation_history
                    WHERE session_id = ?
                    ORDER BY id ASC
                    """,
                    (session_id,),
                ).fetchall()
                saved_rows = conn.execute(
                    """
                    SELECT bucket, item_json
                    FROM saved_items
                    WHERE session_id = ?
                    ORDER BY id ASC
                    """,
                    (session_id,),
                ).fetchall()

        saved: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in SAVE_BUCKETS}
        for row in saved_rows:
            bucket = str(row["bucket"])
            if bucket not in saved:
                continue
            try:
                saved[bucket].append(json.loads(str(row["item_json"])))
            except json.JSONDecodeError:
                continue

        return {
            "conversation_history": [{"role": str(row["role"]), "content": str(row["content"])} for row in history_rows],
            "structured_symptom_list": json.loads(str(session_row["structured_symptom_list"])) if session_row else [],
            "active_agents": json.loads(str(session_row["active_agents"])) if session_row else [],
            "audit_log": list(saved["audit_logs"]),
            "saved": saved,
            "updated_at": str(session_row["updated_at"]) if session_row else datetime.now(UTC).isoformat(),
        }

    def append_history(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            with self._connection() as conn:
                self._ensure_session(conn, session_id)
                now = datetime.now(UTC).isoformat()
                conn.execute(
                    """
                    INSERT INTO conversation_history (session_id, role, content, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, role, content, now),
                )
                conn.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?", (now, session_id))

    def set_structured_symptom_list(self, session_id: str, symptoms: list[str]) -> None:
        with self._lock:
            with self._connection() as conn:
                self._ensure_session(conn, session_id)
                now = datetime.now(UTC).isoformat()
                conn.execute(
                    """
                    UPDATE sessions
                    SET structured_symptom_list = ?, updated_at = ?
                    WHERE session_id = ?
                    """,
                    (json.dumps(symptoms, ensure_ascii=True), now, session_id),
                )

    def set_active_agents(self, session_id: str, agents: list[str]) -> None:
        with self._lock:
            with self._connection() as conn:
                self._ensure_session(conn, session_id)
                now = datetime.now(UTC).isoformat()
                conn.execute(
                    """
                    UPDATE sessions
                    SET active_agents = ?, updated_at = ?
                    WHERE session_id = ?
                    """,
                    (json.dumps(agents, ensure_ascii=True), now, session_id),
                )

    def append_audit_log(self, session_id: str, item: dict[str, Any]) -> None:
        with self._lock:
            with self._connection() as conn:
                self._ensure_session(conn, session_id)
                now = datetime.now(UTC).isoformat()
                conn.execute(
                    """
                    INSERT INTO saved_items (session_id, bucket, item_json, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, "audit_logs", json.dumps(item, ensure_ascii=True), now),
                )
                conn.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?", (now, session_id))

    def save(self, session_id: str, bucket: str, item: dict[str, Any]) -> None:
        if bucket not in SAVE_BUCKETS:
            raise ValueError(f"bucket must be one of {sorted(SAVE_BUCKETS)}")
        with self._lock:
            with self._connection() as conn:
                self._ensure_session(conn, session_id)
                now = datetime.now(UTC).isoformat()
                conn.execute(
                    """
                    INSERT INTO saved_items (session_id, bucket, item_json, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, bucket, json.dumps(item, ensure_ascii=True), now),
                )
                conn.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?", (now, session_id))

    def list_saved(self, session_id: str, bucket: str) -> list[dict[str, Any]]:
        if bucket not in SAVE_BUCKETS:
            raise ValueError(f"bucket must be one of {sorted(SAVE_BUCKETS)}")
        with self._lock:
            with self._connection() as conn:
                self._ensure_session(conn, session_id)
                rows = conn.execute(
                    """
                    SELECT item_json
                    FROM saved_items
                    WHERE session_id = ? AND bucket = ?
                    ORDER BY id ASC
                    """,
                    (session_id, bucket),
                ).fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            try:
                parsed = json.loads(str(row["item_json"]))
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                items.append(parsed)
        return items

    def delete_session(self, session_id: str) -> dict[str, int]:
        with self._lock:
            with self._connection() as conn:
                history_deleted = conn.execute(
                    "DELETE FROM conversation_history WHERE session_id = ?",
                    (session_id,),
                ).rowcount
                saved_deleted = conn.execute(
                    "DELETE FROM saved_items WHERE session_id = ?",
                    (session_id,),
                ).rowcount
                sessions_deleted = conn.execute(
                    "DELETE FROM sessions WHERE session_id = ?",
                    (session_id,),
                ).rowcount

        return {
            "conversation_history": int(history_deleted or 0),
            "saved_items": int(saved_deleted or 0),
            "sessions": int(sessions_deleted or 0),
        }
