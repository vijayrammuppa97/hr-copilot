"""
Case CRUD, workflow progression, and escalation logic for onboarding cases.
"""

import uuid
import logging
from datetime import datetime, timezone

from database import _connect
from workflow import STAGES, STAGE_MAP, get_next_stage

logger = logging.getLogger("hr_copilot.cases")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Case creation ─────────────────────────────────────────────────────────── #

def create_case(
    employee_name: str,
    employee_email: str,
    employee_id: str = "",
    department: str = "",
    role: str = "",
    manager_name: str = "",
    start_date: str = "",
) -> dict:
    case_id = f"OB-{uuid.uuid4().hex[:8].upper()}"
    now = _now()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO onboarding_cases
               (case_id, employee_name, employee_email, employee_id, department, role,
                manager_name, start_date, current_stage, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'document_collection', 'active', ?, ?)""",
            (case_id, employee_name, employee_email, employee_id,
             department, role, manager_name, start_date, now, now),
        )
        # Pre-seed workflow step rows for all 7 stages
        for stage in STAGES:
            for item in stage.items:
                conn.execute(
                    "INSERT INTO case_workflow_steps (case_id, stage_id, item_id, status) VALUES (?, ?, ?, 'pending')",
                    (case_id, stage.id, item.id),
                )
    logger.info("Created case %s for %s (%s)", case_id, employee_name, employee_email)
    return get_case(case_id)  # type: ignore[return-value]


# ── Case retrieval ────────────────────────────────────────────────────────── #

def get_case(case_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM onboarding_cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        if not row:
            return None
        case = dict(row)
        case["workflow"] = _get_workflow_progress(conn, case_id)
        case["escalations"] = _get_escalations(conn, case_id)
    return case


def _get_workflow_progress(conn, case_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT stage_id, item_id, status, completed_at FROM case_workflow_steps WHERE case_id = ? ORDER BY id",
        (case_id,),
    ).fetchall()

    step_map: dict[str, dict[str, dict]] = {}
    for row in rows:
        step_map.setdefault(row["stage_id"], {})[row["item_id"]] = {
            "status": row["status"],
            "completed_at": row["completed_at"],
        }

    result = []
    for stage in STAGES:
        items_state = step_map.get(stage.id, {})
        completed = sum(1 for v in items_state.values() if v["status"] == "completed")
        total = len(stage.items)
        if completed == total:
            stage_status = "completed"
        elif completed > 0:
            stage_status = "in_progress"
        else:
            stage_status = "pending"

        result.append({
            "stage_id": stage.id,
            "name": stage.name,
            "icon": stage.icon,
            "description": stage.description,
            "total_items": total,
            "completed_items": completed,
            "status": stage_status,
            "items": [
                {
                    "id": item.id,
                    "label": item.label,
                    "description": item.description,
                    "status": items_state.get(item.id, {}).get("status", "pending"),
                    "completed_at": items_state.get(item.id, {}).get("completed_at"),
                }
                for item in stage.items
            ],
        })
    return result


def _get_escalations(conn, case_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, reason, status, escalated_by, created_at, resolved_at FROM escalations WHERE case_id = ? ORDER BY id DESC",
        (case_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_cases(limit: int = 200) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM onboarding_cases ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Workflow actions ──────────────────────────────────────────────────────── #

def complete_item(case_id: str, stage_id: str, item_id: str) -> dict | None:
    now = _now()
    with _connect() as conn:
        conn.execute(
            """UPDATE case_workflow_steps
               SET status = 'completed', completed_at = ?
               WHERE case_id = ? AND stage_id = ? AND item_id = ?""",
            (now, case_id, stage_id, item_id),
        )
        conn.execute(
            "UPDATE onboarding_cases SET updated_at = ? WHERE case_id = ?", (now, case_id)
        )
    logger.info("Item completed: case=%s stage=%s item=%s", case_id, stage_id, item_id)
    return get_case(case_id)


def advance_stage(case_id: str) -> dict | None:
    case = get_case(case_id)
    if not case:
        return None
    current = case["current_stage"]
    next_stage = get_next_stage(current)
    now = _now()
    new_stage = next_stage if next_stage else current
    new_status = "completed" if next_stage is None else "active"
    with _connect() as conn:
        conn.execute(
            "UPDATE onboarding_cases SET current_stage = ?, status = ?, updated_at = ? WHERE case_id = ?",
            (new_stage, new_status, now, case_id),
        )
    logger.info("Stage advanced: case=%s %s -> %s", case_id, current, new_stage)
    return get_case(case_id)


# ── Escalation ────────────────────────────────────────────────────────────── #

def create_escalation(case_id: str, reason: str, escalated_by: str = "employee") -> dict:
    now = _now()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO escalations (case_id, reason, status, escalated_by, created_at) VALUES (?, ?, 'open', ?, ?)",
            (case_id, reason, escalated_by, now),
        )
        conn.execute(
            "UPDATE onboarding_cases SET status = 'escalated', updated_at = ? WHERE case_id = ?",
            (now, case_id),
        )
    logger.info("Escalation created: case=%s reason=%r", case_id, reason[:80])
    return {
        "status": "escalated",
        "message": (
            "Your case has been escalated to an HR representative. "
            "They will reach out within 1 business day. "
            f"Reference your Case ID: {case_id}"
        ),
    }


# ── Context builder for LLM ───────────────────────────────────────────────── #

def build_case_context(case: dict) -> str:
    """Return a formatted string injected into the LLM system prompt."""
    stage_id = case["current_stage"]
    stage = STAGE_MAP.get(stage_id)
    if not stage:
        return ""

    workflow = case.get("workflow", [])
    current_stage_data = next((s for s in workflow if s["stage_id"] == stage_id), None)

    pending_items = []
    completed_items = []
    if current_stage_data:
        for item in current_stage_data["items"]:
            if item["status"] == "completed":
                completed_items.append(f"✓ {item['label']}")
            else:
                pending_items.append(f"• {item['label']} — {item['description']}")

    completed_stages = [s["name"] for s in workflow if s["status"] == "completed"]
    total_completed = sum(s["completed_items"] for s in workflow)
    total_items = sum(s["total_items"] for s in workflow)

    first_name = case["employee_name"].split()[0]

    lines = [
        f"EMPLOYEE PROFILE",
        f"  Name:        {case['employee_name']} (call them {first_name})",
        f"  Email:       {case['employee_email']}",
        f"  Employee ID: {case.get('employee_id') or 'Not assigned yet'}",
        f"  Role:        {case.get('role') or 'Not specified'}",
        f"  Department:  {case.get('department') or 'Not specified'}",
        f"  Manager:     {case.get('manager_name') or 'Not assigned yet'}",
        f"  Start Date:  {case.get('start_date') or 'Not specified'}",
        f"  Case ID:     {case['case_id']}",
        f"",
        f"ONBOARDING PROGRESS: {total_completed}/{total_items} items complete",
        f"  Completed stages: {', '.join(completed_stages) if completed_stages else 'None yet'}",
        f"",
        f"CURRENT STAGE: {stage.name}",
        f"  Goal: {stage.description}",
        f"  Completed in this stage: {', '.join(completed_items) if completed_items else 'None yet'}",
        f"  Still pending:",
    ]
    if pending_items:
        lines.extend(f"    {p}" for p in pending_items)
    else:
        lines.append("    All items complete — ready to advance to next stage!")

    lines += [
        f"",
        f"YOUR ROLE IN THIS STAGE:",
        f"  {stage.llm_instructions}",
    ]
    return "\n".join(lines)
