"""
Authentication — signup, login, session token management.

Rules:
  - Only @acme.com email addresses are accepted
  - Passwords hashed with SHA-256 + random salt (no external deps)
  - Session tokens are random UUIDs stored in auth_sessions table
  - Tokens expire after 8 hours; verified on every protected call
"""

import hashlib
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

# Deterministic namespace — same email always produces the same user_id
_USER_ID_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')

from database import _connect

logger = logging.getLogger("hr_copilot.auth")

ALLOWED_DOMAIN = "acme.com"
TOKEN_TTL_HOURS = 8
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


# ── Helpers ───────────────────────────────────────────────────────────────── #

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expires() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)).isoformat()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()


def _validate_email(email: str) -> str | None:
    """Return normalised email or None if invalid / wrong domain."""
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        return None
    domain = email.split("@")[1]
    if domain != ALLOWED_DOMAIN:
        return None
    return email


# ── Public API ────────────────────────────────────────────────────────────── #

def signup(email: str, password: str, full_name: str) -> dict:
    """
    Create a new account.
    Returns {"ok": True, "token": ..., "email": ..., "full_name": ...}
    or      {"ok": False, "error": "..."}
    """
    clean_email = _validate_email(email)
    if not clean_email:
        return {"ok": False, "error": f"Only @{ALLOWED_DOMAIN} email addresses are allowed."}

    if len(password) < 8:
        return {"ok": False, "error": "Password must be at least 8 characters."}

    full_name = full_name.strip()
    if not full_name:
        return {"ok": False, "error": "Full name is required."}

    salt = secrets.token_hex(16)
    pwd_hash = _hash_password(password, salt)
    now = _now()

    with _connect() as conn:
        existing = conn.execute(
            "SELECT id FROM auth_users WHERE email = ?", (clean_email,)
        ).fetchone()
        if existing:
            return {"ok": False, "error": "An account with this email already exists."}

        conn.execute(
            """INSERT INTO auth_users (email, full_name, password_hash, salt, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (clean_email, full_name, pwd_hash, salt, now),
        )

    logger.info("New account created: %s", clean_email)
    # Auto-login after signup
    return _create_session(clean_email, full_name)


def login(email: str, password: str) -> dict:
    """
    Authenticate an existing account.
    Returns {"ok": True, "token": ..., "email": ..., "full_name": ...}
    or      {"ok": False, "error": "..."}
    """
    clean_email = _validate_email(email)
    if not clean_email:
        return {"ok": False, "error": f"Only @{ALLOWED_DOMAIN} email addresses are allowed."}

    with _connect() as conn:
        row = conn.execute(
            "SELECT password_hash, salt, full_name, is_active FROM auth_users WHERE email = ?",
            (clean_email,),
        ).fetchone()

    if not row:
        return {"ok": False, "error": "Invalid email or password."}

    if not row["is_active"]:
        return {"ok": False, "error": "Account is deactivated. Contact HR."}

    expected = _hash_password(password, row["salt"])
    if not secrets.compare_digest(expected, row["password_hash"]):
        return {"ok": False, "error": "Invalid email or password."}

    logger.info("Login successful: %s", clean_email)
    return _create_session(clean_email, row["full_name"])


def verify_token(token: str) -> dict | None:
    """
    Validate a session token. Returns user info dict or None if invalid/expired.
    """
    if not token:
        return None
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT email, full_name, expires_at FROM auth_sessions WHERE token = ?",
            (token,),
        ).fetchone()
    if not row:
        return None
    if row["expires_at"] < now:
        _delete_session(token)
        return None
    return {
        "email":     row["email"],
        "full_name": row["full_name"],
        "token":     token,
        "user_id":   email_to_user_id(row["email"]),
    }


def logout(token: str) -> None:
    """Invalidate a session token."""
    _delete_session(token)
    logger.info("Session revoked: %s", token[:8] + "...")


# ── Internal ──────────────────────────────────────────────────────────────── #

def email_to_user_id(email: str) -> str:
    """Deterministic UUID from email — same email always maps to the same user_id."""
    return str(uuid.uuid5(_USER_ID_NAMESPACE, email.lower()))


def _create_session(email: str, full_name: str) -> dict:
    token = str(uuid.uuid4())
    now = _now()
    expires = _expires()
    user_id = email_to_user_id(email)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO auth_sessions (token, email, full_name, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (token, email, full_name, now, expires),
        )
    return {"ok": True, "token": token, "email": email, "full_name": full_name, "user_id": user_id}


def _delete_session(token: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
