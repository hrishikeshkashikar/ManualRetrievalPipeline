"""Auth API — login, register, current user. Fully offline."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.deps import get_current_user, get_current_user_optional
from app.auth.security import create_token, verify_password
from app.auth.store import get_store
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=4)
    role: str = Field(default="user")


class UserPublic(BaseModel):
    id: str
    username: str
    role: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class AuthStatusResponse(BaseModel):
    enabled: bool
    has_users: bool
    allow_register: bool


def _public_user(user: dict) -> UserPublic:
    return UserPublic(
        id=user["id"],
        username=user["username"],
        role=user.get("role", "user"),
    )


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status() -> AuthStatusResponse:
    if not settings.auth_enabled:
        return AuthStatusResponse(enabled=False, has_users=False, allow_register=False)
    store = get_store()
    count = store.count()
    return AuthStatusResponse(
        enabled=True,
        has_users=count > 0,
        allow_register=settings.auth_allow_register or count == 0,
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest) -> AuthResponse:
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Authentication is disabled")
    store = get_store()
    user = store.get_by_username(body.username)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(
        {"sub": user["id"], "username": user["username"], "role": user.get("role", "user")},
        store.secret,
    )
    return AuthResponse(access_token=token, user=_public_user(user))


@router.post("/register", response_model=AuthResponse)
async def register(
    body: RegisterRequest,
    current: dict | None = Depends(get_current_user_optional),
) -> AuthResponse:
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Authentication is disabled")
    store = get_store()
    is_first = store.count() == 0
    is_admin = bool(current and current.get("role") == "admin")
    if not (is_first or settings.auth_allow_register or is_admin):
        raise HTTPException(status_code=403, detail="Registration is closed")
    role = "admin" if is_first else (body.role if is_admin else "user")
    try:
        user = store.create(body.username, body.password, role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    token = create_token(
        {"sub": user["id"], "username": user["username"], "role": user.get("role", "user")},
        store.secret,
    )
    return AuthResponse(access_token=token, user=_public_user(user))


@router.get("/me", response_model=UserPublic)
async def me(current: dict = Depends(get_current_user)) -> UserPublic:
    return _public_user(current)
