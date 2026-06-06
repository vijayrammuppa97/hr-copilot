"""
Profile extractor — parses a single conversation turn (user message)
and returns any profile facts found: tenure, employment type, department, role.

Design:
- Regex only (no LLM call) — fast, deterministic, zero latency overhead
- Returns only fields where a match was found (caller decides whether to update)
- Conservative: only high-confidence patterns trigger an update

Usage:
    facts = extract_profile_facts("I've worked at Acme for 3 years as a full-time engineer")
    # → {"tenure_years": 3.0, "employment_type": "full-time", "role": "engineer"}
"""

import re
import logging

logger = logging.getLogger("hr_copilot.profile_extractor")

# ── Tenure patterns ───────────────────────────────────────────────────────── #

_TENURE_RE = [
    # "I've been working here for 3 years" / "I've worked at Acme for 2.5 years"
    re.compile(r"(?:i[' ]?ve?\s+(?:been\s+)?(?:work(?:ing|ed)|employ(?:ed)?)\s+"
               r"(?:here|at\s+acme|with\s+acme|for\s+acme)?\s*(?:for\s+)?)"
               r"(\d+(?:\.\d+)?)\s+years?", re.I),
    # "3 years of service" / "2 years' experience here"
    re.compile(r"(\d+(?:\.\d+)?)\s+years?\s+(?:of\s+service|experience|working\s+here|at\s+acme)", re.I),
    # "I've been here for 1 year"
    re.compile(r"i[' ]?ve?\s+been\s+here\s+(?:for\s+)?(\d+(?:\.\d+)?)\s+years?", re.I),
    # "joined 2 years ago" / "started 1 year ago"
    re.compile(r"(?:joined|started)\s+(\d+(?:\.\d+)?)\s+years?\s+ago", re.I),
    # "working since X years" (common non-native phrasing)
    re.compile(r"working\s+since\s+(\d+(?:\.\d+)?)\s+years?", re.I),
    # "I am a 3-year employee"
    re.compile(r"(\d+(?:\.\d+)?)[- ]year\s+employee", re.I),
]

# ── Employment type patterns ──────────────────────────────────────────────── #

_EMPLOYMENT_RE = [
    (re.compile(r"\bfull[- ]?time\b", re.I),  "full-time"),
    (re.compile(r"\bpart[- ]?time\b", re.I),  "part-time"),
    (re.compile(r"\bcontract(?:or)?\b", re.I), "contractor"),
    (re.compile(r"\bfreelance\b", re.I),       "contractor"),
    (re.compile(r"\bpermanent\b", re.I),       "full-time"),
]

# ── Department patterns ───────────────────────────────────────────────────── #

_DEPT_RE = [
    # "I work in the Engineering department" / "part of the Sales team"
    re.compile(r"(?:i\s+work\s+in|i[' ]?m\s+in|part\s+of)\s+the\s+([\w\s]{2,30?})\s+"
               r"(?:team|department|dept\.?|division)", re.I),
    # "my department is Finance"
    re.compile(r"(?:my\s+)?department\s+is\s+([\w\s]{2,30})", re.I),
    # "I'm on the Marketing team"
    re.compile(r"i[' ]?m\s+on\s+the\s+([\w\s]{2,20?})\s+team", re.I),
]

_KNOWN_DEPTS = {
    "engineering", "finance", "marketing", "sales", "hr", "human resources",
    "product", "design", "operations", "legal", "it", "data", "analytics",
    "customer success", "support", "procurement", "strategy", "research",
}

# ── Role patterns ─────────────────────────────────────────────────────────── #

_ROLE_RE = [
    # "I work as a Senior Engineer" / "I am an analyst"
    re.compile(r"i(?:\s+am|\s+work\s+as)\s+(?:a\s+|an\s+)([\w\s]{3,40?})"
               r"(?:\s+at\s+acme|\s+here|\s*[.,])", re.I),
    # "my role is Product Manager"
    re.compile(r"my\s+(?:role|title|position)\s+is\s+([\w\s]{3,40})", re.I),
    # "I'm a Data Scientist"
    re.compile(r"i[' ]?m\s+(?:a\s+|an\s+)([\w\s]{3,30?})\s+(?:at\s+acme|here|working)", re.I),
]

_ROLE_STOPWORDS = {
    "working", "here", "new", "old", "senior", "junior", "the", "a", "an",
    "employee", "staff", "member", "person", "one", "looking",
}


def _clean_role(raw: str) -> str | None:
    cleaned = raw.strip().rstrip(".,;").strip()
    if len(cleaned) < 3 or len(cleaned) > 50:
        return None
    words = cleaned.lower().split()
    if all(w in _ROLE_STOPWORDS for w in words):
        return None
    return cleaned.title()


def _clean_dept(raw: str) -> str | None:
    cleaned = raw.strip().rstrip(".,;").strip().lower()
    if cleaned in _KNOWN_DEPTS or any(kw in cleaned for kw in _KNOWN_DEPTS):
        return cleaned.title()
    return None


def extract_profile_facts(text: str) -> dict:
    """
    Parse a user message and return a dict of discovered profile facts.
    Only fields with confident matches are included.
    """
    facts: dict = {}

    # Tenure
    for pattern in _TENURE_RE:
        m = pattern.search(text)
        if m:
            try:
                val = float(m.group(1))
                if 0 < val <= 50:          # sanity: 0–50 years of service
                    facts["tenure_years"] = val
                    logger.debug("Extracted tenure_years=%.1f from %r", val, text[:60])
                    break
            except ValueError:
                pass

    # Employment type
    for pattern, label in _EMPLOYMENT_RE:
        if pattern.search(text):
            facts["employment_type"] = label
            logger.debug("Extracted employment_type=%r", label)
            break

    # Department
    for pattern in _DEPT_RE:
        m = pattern.search(text)
        if m:
            dept = _clean_dept(m.group(1))
            if dept:
                facts["department"] = dept
                logger.debug("Extracted department=%r", dept)
                break

    # Role
    for pattern in _ROLE_RE:
        m = pattern.search(text)
        if m:
            role = _clean_role(m.group(1))
            if role:
                facts["role"] = role
                logger.debug("Extracted role=%r", role)
                break

    return facts
