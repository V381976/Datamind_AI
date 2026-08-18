from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class ChatHistoryStore:
    """Persistent chat history that survives backend restarts."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        root = Path(__file__).resolve().parents[1]
        self.db_path = Path(db_path) if db_path else root / "data" / "chat_history.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    tool TEXT,
                    table_name TEXT,
                    plan_json TEXT,
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at)"
            )
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def ensure_conversation(self, conversation_id: Optional[str] = None) -> str:
        conversation_id = conversation_id or str(uuid.uuid4())
        now = self._now()
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO conversations (id, created_at, updated_at) VALUES (?, ?, ?)",
                    (conversation_id, now, now),
                )
            else:
                conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
            conn.commit()
        return conversation_id

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool: Optional[str] = None,
        table_name: Optional[str] = None,
        plan: Optional[Dict[str, Any]] = None,
        result: Optional[Any] = None,
        message_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        conversation_id = self.ensure_conversation(conversation_id)
        message_id = message_id or str(uuid.uuid4())
        timestamp = timestamp or datetime.now().strftime("%I:%M %p")
        created_at = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    id, conversation_id, role, content, timestamp, tool, table_name, plan_json, result_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    role,
                    content,
                    timestamp,
                    tool,
                    table_name,
                    json.dumps(plan) if plan is not None else None,
                    json.dumps(result) if result is not None else None,
                    created_at,
                ),
            )
            conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (created_at, conversation_id))
            conn.commit()
        return {
            "id": message_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "tool": tool,
            "table": table_name,
            "plan": plan,
            "result": result,
        }

    def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, conversation_id, role, content, timestamp, tool, table_name, plan_json, result_json
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (conversation_id,),
            ).fetchall()
        messages = []
        for row in rows:
            messages.append(
                {
                    "id": row["id"],
                    "conversation_id": row["conversation_id"],
                    "role": row["role"],
                    "content": row["content"],
                    "timestamp": row["timestamp"],
                    "tool": row["tool"],
                    "table": row["table_name"],
                    "plan": json.loads(row["plan_json"]) if row["plan_json"] else None,
                    "result": json.loads(row["result_json"]) if row["result_json"] else None,
                }
            )
        return messages

    def list_conversations(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.created_at, c.updated_at,
                       (SELECT content FROM messages m WHERE m.conversation_id = c.id AND m.role = 'user'
                        ORDER BY m.created_at ASC LIMIT 1) AS first_question
                FROM conversations c
                ORDER BY c.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "first_question": row["first_question"],
            }
            for row in rows
        ]
