"""Auth helpers + HTTP middleware. Protects API routes, not static UI files."""

from __future__ import annotations

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.auth.security import decode_token
from app.auth.store import get_store
from app.config import settings

PUBLIC_EXACT = {
    "/health",
    "/auth/login",
    "/auth/register",
    "/auth/status",
    "/docs",
    "/openapi.json",
    "/redoc",
}

PUBLIC_PREFIXES = (
    "/css/",
    "/js/",
    "/assets/",
)

API_PREFIXES = (
    "/ingest",
    "/query",
    "/config",
    "/auth/me",
)


def _extract_token(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    cookie = request.cookies.get("mr_token")
    if cookie:
        return cookie
    return None


def resolve_user(request: Request) -> dict | None:
    token = _extract_token(request)
    if not token:
        return None
    store = get_store()
    payload = decode_token(token, store.secret)
    if not payload:
        return None
    user = store.get_by_id(str(payload.get("sub", "")))
    return user


async def get_current_user(request: Request) -> dict:
    if not settings.auth_enabled:
        return {"id": "anonymous", "username": "anonymous", "role": "admin"}
    user = resolve_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def get_current_user_optional(request: Request) -> dict | None:
    if not settings.auth_enabled:
        return None
    return resolve_user(request)


def _is_public(path: str) -> bool:
    if path in PUBLIC_EXACT or path == "/":
        return True
    if any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return True
    if path.endswith((".css", ".js", ".html", ".ico", ".svg", ".png", ".woff2")):
        return True
    return False


def _is_protected_api(path: str) -> bool:
    return any(path == p or path.startswith(p) for p in API_PREFIXES)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.auth_enabled:
            return await call_next(request)

        path = request.url.path
        if _is_public(path) and not _is_protected_api(path):
            return await call_next(request)

        if _is_protected_api(path):
            user = resolve_user(request)
            if not user:
                return JSONResponse({"detail": "Not authenticated"}, status_code=401)
            request.state.user = user

        return await call_next(request)
