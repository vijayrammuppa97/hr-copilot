"""
SQLite persistence layer — audit trail for all HR Copilot conversations.

Tables:
  conversations — one row per session (id, created_at, updated_at)
  messages      — every user / assistant turn
  feedback      — thumbs-up / thumbs-down signals
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("hr_copilot.db")

DB_PATH = Path(__file__).parent.parent / "data" / "hr_copilot.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id         TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT    NOT NULL,
                role            TEXT    NOT NULL,
                content         TEXT    NOT NULL,
                sources         TEXT,
                confidence      REAL,
                timestamp       TEXT    NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id      TEXT    NOT NULL,
                conversation_id TEXT    NOT NULL,
                value           TEXT    NOT NULL,
                timestamp       TEXT    NOT NULL
            );

            -- Onboarding case per new hire
            CREATE TABLE IF NOT EXISTS onboarding_cases (
                case_id        TEXT PRIMARY KEY,
                employee_name  TEXT NOT NULL,
                employee_email TEXT NOT NULL,
                employee_id    TEXT DEFAULT '',
                department     TEXT DEFAULT '',
                role           TEXT DEFAULT '',
                manager_name   TEXT DEFAULT '',
                start_date     TEXT DEFAULT '',
                current_stage  TEXT DEFAULT 'document_collection',
                status         TEXT DEFAULT 'active',
                created_at     TEXT NOT NULL,
                updated_at     TEXT NOT NULL
            );

            -- Per-item completion tracking across all 7 stages
            CREATE TABLE IF NOT EXISTS case_workflow_steps (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id      TEXT NOT NULL,
                stage_id     TEXT NOT NULL,
                item_id      TEXT NOT NULL,
                status       TEXT DEFAULT 'pending',
                notes        TEXT DEFAULT '',
                completed_at TEXT,
                FOREIGN KEY (case_id) REFERENCES onboarding_cases(case_id)
            );

            -- Documents uploaded per case
            CREATE TABLE IF NOT EXISTS case_documents (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id     TEXT NOT NULL,
                doc_type    TEXT NOT NULL,
                filename    TEXT DEFAULT '',
                status      TEXT DEFAULT 'uploaded',
                uploaded_at TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES onboarding_cases(case_id)
            );

            -- Escalations raised by employee or system
            CREATE TABLE IF NOT EXISTS escalations (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id       TEXT NOT NULL,
                reason        TEXT NOT NULL,
                status        TEXT DEFAULT 'open',
                escalated_by  TEXT DEFAULT 'employee',
                assigned_to   TEXT DEFAULT '',
                created_at    TEXT NOT NULL,
                resolved_at   TEXT,
                notes         TEXT DEFAULT '',
                FOREIGN KEY (case_id) REFERENCES onboarding_cases(case_id)
            );

            -- Named users with random usernames + profile attributes
            CREATE TABLE IF NOT EXISTS users (
                user_id         TEXT PRIMARY KEY,
                username        TEXT NOT NULL,
                created_at      TEXT NOT NULL,
                last_seen       TEXT NOT NULL,
                tenure_years    REAL DEFAULT NULL,
                employment_type TEXT DEFAULT NULL,
                department      TEXT DEFAULT NULL,
                role            TEXT DEFAULT NULL
            );

            -- One session per conversation, linked to a user
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id      TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                case_id         TEXT,
                message_count   INTEGER DEFAULT 0,
                started_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            -- Per-query evaluation metrics
            CREATE TABLE IF NOT EXISTS evaluation_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                query           TEXT NOT NULL,
                recall_at_k     REAL,
                faithfulness    REAL,
                relevance_score REAL,
                k               INTEGER DEFAULT 3,
                timestamp       TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_cid   ON messages(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_feedback_cid   ON feedback(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_steps_case     ON case_workflow_steps(case_id);
            CREATE INDEX IF NOT EXISTS idx_docs_case      ON case_documents(case_id);
            CREATE INDEX IF NOT EXISTS idx_escl_case      ON escalations(case_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_user  ON user_sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_eval_cid       ON evaluation_log(conversation_id);
        """)
    # Migrate existing databases — add profile columns if missing
    _migrate_user_profile_columns(conn)
    logger.info("SQLite database ready at %s", DB_PATH)


def _migrate_user_profile_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    for col, definition in [
        ("tenure_years",    "REAL DEFAULT NULL"),
        ("employment_type", "TEXT DEFAULT NULL"),
        ("department",      "TEXT DEFAULT NULL"),
        ("role",            "TEXT DEFAULT NULL"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
            logger.info("Migrated users table: added column %s", col)


def update_user_profile(
    user_id: str,
    tenure_years:    float | None = None,
    employment_type: str   | None = None,
    department:      str   | None = None,
    role:            str   | None = None,
) -> dict | None:
    """Update only the profile fields that are provided (non-None)."""
    fields, values = [], []
    if tenure_years    is not None: fields.append("tenure_years = ?");    values.append(tenure_years)
    if employment_type is not None: fields.append("employment_type = ?"); values.append(employment_type)
    if department      is not None: fields.append("department = ?");      values.append(department)
    if role            is not None: fields.append("role = ?");            values.append(role)
    if not fields:
        return None
    values.append(user_id)
    with _connect() as conn:
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?", values)
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def save_exchange(
    conversation_id: str,
    user_message: str,
    assistant_message: str,
    sources: list[str],
    confidence: float,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO conversations (id, created_at, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (conversation_id, now, now),
        )
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, sources, confidence, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (conversation_id, "user", user_message, None, None, now),
        )
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, sources, confidence, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (conversation_id, "assistant", assistant_message, json.dumps(sources), round(confidence, 2), now),
        )
    logger.debug("Saved exchange cid=%r", conversation_id)


def save_feedback(message_id: str, conversation_id: str, value: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO feedback (message_id, conversation_id, value, timestamp) VALUES (?, ?, ?, ?)",
            (message_id, conversation_id, value, datetime.now(timezone.utc).isoformat()),
        )
    logger.debug("Saved feedback cid=%r value=%r", conversation_id, value)


def get_conversations(limit: int = 100) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.created_at, c.updated_at,
                   COUNT(m.id)                                             AS total_messages,
                   SUM(CASE WHEN m.role = 'user' THEN 1 ELSE 0 END)       AS user_turns,
                   COALESCE(AVG(CASE WHEN m.role = 'assistant' THEN m.confidence END), 0) AS avg_confidence
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation_messages(conversation_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content, sources, confidence, timestamp
            FROM messages WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["sources"] = json.loads(d["sources"]) if d["sources"] else []
        result.append(d)
    return result


def get_feedback_summary() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT value, COUNT(*) AS count FROM feedback GROUP BY value",
        ).fetchall()
    return [dict(r) for r in rows]


# ── Observability queries ─────────────────────────────────────────────────── #

def get_admin_stats() -> dict:
    with _connect() as conn:
        total_msgs   = conn.execute("SELECT COUNT(*) FROM messages WHERE role='user'").fetchone()[0]
        total_users  = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_cases  = conn.execute("SELECT COUNT(*) FROM onboarding_cases").fetchone()[0]
        avg_conf     = conn.execute("SELECT AVG(confidence) FROM messages WHERE role='assistant' AND confidence IS NOT NULL").fetchone()[0]
        today        = datetime.now(timezone.utc).date().isoformat()
        msgs_today   = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE role='user' AND timestamp >= ?", (today,)
        ).fetchone()[0]
        escalations  = conn.execute("SELECT COUNT(*) FROM escalations WHERE status='open'").fetchone()[0]
    return {
        "total_messages":      total_msgs,
        "total_users":         total_users,
        "total_cases":         total_cases,
        "avg_confidence":      round(avg_conf or 0, 3),
        "messages_today":      msgs_today,
        "open_escalations":    escalations,
    }


def get_top_interactions(limit: int = 20) -> list[dict]:
    """Most frequent user queries grouped by normalised content."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT content AS query,
                   COUNT(*) AS frequency,
                   MAX(timestamp) AS last_seen
            FROM messages
            WHERE role = 'user'
            GROUP BY LOWER(TRIM(content))
            ORDER BY frequency DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_confidence_distribution() -> list[dict]:
    """Bucket confidence scores into 10% bands for histogram."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT CAST(ROUND(confidence * 10) AS INTEGER) * 10 AS bucket,
                   COUNT(*) AS count
            FROM messages
            WHERE role = 'assistant' AND confidence IS NOT NULL
            GROUP BY bucket
            ORDER BY bucket
            """,
        ).fetchall()
    return [dict(r) for r in rows]


def get_messages_over_time(days: int = 30) -> list[dict]:
    """Daily message count for the last N days."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT DATE(timestamp) AS date, COUNT(*) AS count
            FROM messages
            WHERE role = 'user'
              AND timestamp >= DATE('now', ?)
            GROUP BY DATE(timestamp)
            ORDER BY date
            """,
            (f"-{days} days",),
        ).fetchall()
    return [dict(r) for r in rows]
