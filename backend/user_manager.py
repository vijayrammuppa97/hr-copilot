"""
User identity management.

Each browser session gets a random username (adjective-animal-4digits)
and a UUID-based user_id. Both are stored in localStorage on the frontend
and registered with the backend on first request.

Session = one continuous conversation. A session ends when the user closes
the tab or starts a new chat. Sessions are stored in SQLite and returned
as a date-grouped tree for the session history sidebar.
"""

import logging
import random
import uuid
from datetime import datetime, timezone

from database import _connect

logger = logging.getLogger("hr_copilot.users")

# ── Username word lists ───────────────────────────────────────────────────── #

_ADJECTIVES = [
    "swift", "calm", "bright", "bold", "quiet", "sharp", "clear",
    "quick", "warm", "cool", "wise", "brave", "keen", "agile",
    "steady", "noble", "vivid", "nimble", "clever", "eager",
]

_ANIMALS = [
    "falcon", "eagle", "panda", "tiger", "wolf", "lynx", "otter",
    "raven", "crane", "bison", "koala", "gecko", "finch", "heron",
    "badger", "lemur", "dingo", "moose", "viper", "quail",
]


def generate_username() -> str:
    adj    = random.choice(_ADJECTIVES)
    animal = random.choice(_ANIMALS)
    num    = random.randint(1000, 9999)
    return f"{adj}-{animal}-{num}"


def generate_user_id() -> str:
    return str(uuid.uuid4())


# ── DB helpers ────────────────────────────────────────────────────────────── #

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def register_user(user_id: str, username: str) -> dict:
    now = _now()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO users (user_id, username, created_at, last_seen)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET last_seen = excluded.last_seen""",
            (user_id, username, now, now),
        )
    return {"user_id": user_id, "username": username}


def get_user(user_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def touch_user(user_id: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE users SET last_seen = ? WHERE user_id = ?", (_now(), user_id))


# ── Session management ────────────────────────────────────────────────────── #

def create_session(user_id: str, conversation_id: str, case_id: str | None = None) -> dict:
    now = _now()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO user_sessions (session_id, user_id, conversation_id, case_id, started_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET updated_at = excluded.updated_at""",
            (conversation_id, user_id, conversation_id, case_id, now, now),
        )
    return {"session_id": conversation_id, "started_at": now}


def update_session(conversation_id: str, message_count: int | None = None) -> None:
    now = _now()
    with _connect() as conn:
        if message_count is not None:
            conn.execute(
                "UPDATE user_sessions SET updated_at = ?, message_count = message_count + 1 WHERE session_id = ?",
                (now, conversation_id),
            )
        else:
            conn.execute(
                "UPDATE user_sessions SET updated_at = ? WHERE session_id = ?",
                (now, conversation_id),
            )


def get_user_sessions(user_id: str) -> list[dict]:
    """Return all sessions for a user, newest first, with preview text."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT s.session_id, s.started_at, s.updated_at, s.message_count,
                   m.content AS preview
            FROM user_sessions s
            LEFT JOIN (
                SELECT conversation_id, content
                FROM messages
                WHERE role = 'user'
                GROUP BY conversation_id
                HAVING MIN(id)
            ) m ON m.conversation_id = s.session_id
            WHERE s.user_id = ?
            ORDER BY s.updated_at DESC
            LIMIT 100
            """,
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_users(limit: int = 500) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT user_id, username, created_at, last_seen FROM users ORDER BY last_seen DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
