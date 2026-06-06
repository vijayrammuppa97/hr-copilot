"""
Query Rewriter — expands a user query into multiple search-optimised variants.

Two-stage approach:
  1. Rule-based expansion  — instant, no LLM cost
     - Expands HR abbreviations (PTO, WFH, BGV, etc.)
     - Adds synonyms for common leave/policy terms
     - Normalises phrasing

  2. LLM multi-query expansion — async, 3 alternative phrasings
     - Focused prompt with num_predict=80 keeps latency low (~3s on CPU)
     - Disabled by setting QUERY_REWRITE_LLM=false in .env
     - On failure, falls back to rule-based only

The combined query set is fed into the Hybrid Search pipeline.
Multiple queries increase recall significantly — especially for queries
where the user's wording doesn't match the policy document's wording.
"""

import logging
import os
import re

import ollama

logger = logging.getLogger("hr_copilot.query_rewriter")

# ── HR abbreviation & synonym map ─────────────────────────────────────────── #

_ABBREV: dict[str, str] = {
    r"\bpto\b":         "annual leave entitlement accrues calendar year",
    r"\bwfh\b":         "work from home remote",
    r"\bwfa\b":         "work from anywhere international remote",
    r"\bbgv\b":         "background verification check",
    r"\bpip\b":         "performance improvement plan",
    r"\bposh\b":        "prevention of sexual harassment",
    r"\beap\b":         "employee assistance programme",
    r"\bhrms\b":        "hr management system portal",
    r"\blms\b":         "learning management system training",
    r"\bctc\b":         "cost to company salary package",
    r"\bpf\b":          "provident fund deduction",
    r"\bpt\b":          "professional tax",
    r"\bmfa\b":         "multi factor authentication security",
    r"\bvpn\b":         "virtual private network security",
    r"\bsla\b":         "service level agreement",
    r"\bhr\b":          "human resources",
    r"\bpl\b":          "paternity leave paid leave",
    r"\bml\b":          "maternity leave paid leave",
    r"\bcl\b":          "casual leave annual leave",
    r"\bsl\b":          "sick leave medical leave",
    r"\bel\b":          "earned leave annual leave entitlement",
}

_SYNONYMS: dict[str, str] = {
    # Annual leave synonyms — use KB-specific terms: "entitlement", "accrues", "calendar year"
    "vacation":           "annual leave entitlement",
    "holiday":            "annual leave entitlement",
    "day off":            "annual leave",
    "days off":           "annual leave entitlement days per year",
    "time off":           "annual leave entitlement",
    "pto":                "annual leave entitlement paid leave accrues calendar year",
    "paid time off":      "annual leave entitlement accrues",
    # Carry-forward — use exact KB phrase "carry-forward" and "roll over"
    "rollover":           "carry-forward annual leave roll over unused days forfeited",
    "roll over":          "carry-forward annual leave unused days",
    "vacation rollover":  "carry-forward annual leave roll over unused days december",
    "unused leave":       "carry-forward annual leave roll over forfeited",
    "unused days":        "carry-forward annual leave unused",
    # Sick leave
    "flu":                "sick leave illness",
    "cold":               "sick leave illness",
    "unwell":             "sick leave medical",
    "sick day":           "sick leave",
    "call in sick":       "sick leave absence",
    # Parental leave — use KB-specific discriminator terms
    "pregnant":           "maternity leave birthing parent due date",
    "pregnancy":          "maternity leave birthing parent due date pre-natal",
    "expecting":          "maternity leave due date",
    "baby":               "maternity paternity parental leave",
    # Paternity — "non-birthing" and "birth registration" are unique to section 1.10
    "dad":                "paternity leave non-birthing parent secondary caregiver",
    "new dad":            "paternity leave non-birthing parent birth registration",
    "father":             "paternity leave non-birthing",
    "birth of child":     "paternity leave non-birthing birth registration certificate",
    "newborn":            "paternity leave non-birthing parent",
    "adopt":              "adoption leave child placement adoptive",
    # Termination
    "fired":              "termination dismissal",
    "quit":               "resignation notice period",
    "resign":             "resignation notice period",
    # Equipment
    "stolen":             "stolen lost theft equipment reporting IT security",
    "broken":             "damaged equipment replacement",
    # Work & misc
    "internet":           "broadband connectivity remote work subsidy",
    "bonus":              "incentive performance pay compensation",
    "raise":              "salary increment compensation",
    "complaint":          "grievance formal complaint procedure",
    "raise a complaint":  "formal grievance procedure",
    "harassed":           "harassment posh grievance",
    "bullied":            "harassment bullying grievance",
    "promotion":          "career development performance appraisal",
    "training":           "learning development LMS course",
    "reimbursement":      "expense claim reimbursement",
    "insurance":          "health benefits medical cover",
    "jury":               "jury duty civic leave court",
    "bereavement":        "bereavement leave death family compassionate",
    "funeral":            "bereavement leave emergency compassionate",
    "work from home":     "remote work WFH policy",
    "remote working":     "remote work policy eligible",
}


def _rule_expand(query: str) -> str:
    """Apply abbreviation and synonym expansion to the query."""
    q = query.lower()
    for pattern, replacement in _ABBREV.items():
        q = re.sub(pattern, replacement, q, flags=re.IGNORECASE)
    for term, expansion in _SYNONYMS.items():
        if term in q:
            q = q + " " + expansion
    return q.strip()


# ── LLM-based multi-query expansion ──────────────────────────────────────── #

_REWRITE_PROMPT = """\
You are a search query optimizer for an HR policy knowledge base.

Given the employee question below, write 2 alternative search queries \
that would retrieve the relevant HR policy sections. Focus on:
- Policy section names (e.g. "Annual Leave", "Sick Leave Documentation")
- Key terms the policy document would use
- Specific actions or requirements

Employee question: {query}

Write exactly 2 alternative queries, one per line, no bullets or numbers:"""


class QueryRewriter:
    def __init__(self, model: str, host: str = "http://localhost:11434") -> None:
        self._model  = model
        self._client = ollama.Client(host=host)
        self._use_llm = os.getenv("QUERY_REWRITE_LLM", "true").lower() == "true"
        logger.info("QueryRewriter ready — model=%s llm_rewrite=%s", model, self._use_llm)

    def expand(self, query: str) -> list[str]:
        """
        Returns a deduplicated list of queries: original + rule-expanded + LLM variants.
        Falls back gracefully if LLM is unavailable.
        """
        queries: list[str] = [query.strip()]

        # 1. Rule-based expansion (always fast)
        expanded = _rule_expand(query)
        if expanded != query.lower():
            queries.append(expanded)

        # 2. LLM multi-query (optional, may be slow on CPU)
        if self._use_llm:
            try:
                resp = self._client.generate(
                    model=self._model,
                    prompt=_REWRITE_PROMPT.format(query=query),
                    options={"num_predict": 80, "temperature": 0.1},
                    keep_alive=-1,
                )
                lines = [l.strip() for l in resp["response"].strip().split("\n") if l.strip()]
                queries.extend(lines[:2])
            except Exception as exc:
                logger.warning("LLM query rewrite failed (using rule-based only): %s", exc)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for q in queries:
            key = q.lower().strip()
            if key not in seen and key:
                seen.add(key)
                unique.append(q)

        logger.info("Query expansion: %r → %d variants", query[:60], len(unique))
        return unique
