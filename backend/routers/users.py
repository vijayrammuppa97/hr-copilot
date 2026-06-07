from fastapi import APIRouter, HTTPException

from user_manager import (
    register_user, get_user, touch_user, get_user_sessions,
    get_all_users, update_user_profile, generate_username, generate_user_id,
)
from models.chat import RegisterUserRequest, UpdateProfileRequest

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("/register")
async def register(body: RegisterUserRequest) -> dict:
    uid      = body.user_id  or generate_user_id()
    username = body.username or generate_username()
    existing = get_user(uid)
    if existing:
        touch_user(uid)
        if any(v is not None for v in [body.tenure_years, body.employment_type, body.department, body.role]):
            update_user_profile(uid, body.tenure_years, body.employment_type, body.department, body.role)
        return get_user(uid) or existing
    return register_user(uid, username, body.tenure_years, body.employment_type, body.department, body.role)


@router.get("/{user_id}")
async def get_profile(user_id: str) -> dict:
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    touch_user(user_id)
    return user


@router.patch("/{user_id}/profile")
async def patch_profile(user_id: str, body: UpdateProfileRequest) -> dict:
    if not get_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    updated = update_user_profile(
        user_id,
        tenure_years=body.tenure_years,
        employment_type=body.employment_type,
        department=body.department,
        role=body.role,
    )
    return updated or {}


@router.get("/{user_id}/sessions")
async def user_sessions(user_id: str) -> list[dict]:
    if not get_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return get_user_sessions(user_id)
