from fastapi import APIRouter, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address

from auth import (
    signup as auth_signup,
    login  as auth_login,
    logout as auth_logout,
    verify_token,
)
from models.auth import SignupRequest, LoginRequest

router  = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)
_bearer = HTTPBearer(auto_error=False)


@router.post("/signup")
@limiter.limit("5/minute")
async def signup(request: Request, body: SignupRequest) -> dict:
    result = auth_signup(body.email, body.password, body.full_name)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {
        "token":     result["token"],
        "email":     result["email"],
        "full_name": result["full_name"],
        "user_id":   result["user_id"],
    }


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest) -> dict:
    result = auth_login(body.email, body.password)
    if not result["ok"]:
        raise HTTPException(status_code=401, detail=result["error"])
    return {
        "token":     result["token"],
        "email":     result["email"],
        "full_name": result["full_name"],
        "user_id":   result["user_id"],
    }


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials | None = Security(_bearer)) -> dict:
    if credentials:
        auth_logout(credentials.credentials)
    return {"status": "logged out"}


@router.get("/me")
async def me(credentials: HTTPAuthorizationCredentials | None = Security(_bearer)) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = verify_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please log in again.")
    return user
