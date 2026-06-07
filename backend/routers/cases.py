from fastapi import APIRouter, Request
from fastapi.exceptions import HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

from case_manager import (
    create_case, get_case, get_all_cases,
    complete_item, advance_stage, create_escalation,
)
from models.onboarding import CreateCaseRequest, CompleteItemRequest, EscalateRequest

router  = APIRouter(prefix="/api/cases", tags=["onboarding"])
limiter = Limiter(key_func=get_remote_address)


@router.post("")
@limiter.limit("10/minute")
async def create_onboarding_case(request: Request, body: CreateCaseRequest) -> dict:
    return create_case(
        employee_name=body.employee_name,
        employee_email=body.employee_email,
        employee_id=body.employee_id,
        department=body.department,
        role=body.role,
        manager_name=body.manager_name,
        start_date=body.start_date,
    )


@router.get("/{case_id}")
async def get_onboarding_case(case_id: str) -> dict:
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/{case_id}/complete-item")
async def mark_item_complete(case_id: str, body: CompleteItemRequest) -> dict:
    if not get_case(case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    return complete_item(case_id, body.stage_id, body.item_id)  # type: ignore[return-value]


@router.post("/{case_id}/advance-stage")
async def advance_onboarding_stage(case_id: str) -> dict:
    if not get_case(case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    return advance_stage(case_id)  # type: ignore[return-value]


@router.post("/{case_id}/escalate")
@limiter.limit("5/minute")
async def escalate_case(request: Request, case_id: str, body: EscalateRequest) -> dict:
    if not get_case(case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    return create_escalation(case_id, body.reason, body.escalated_by)
