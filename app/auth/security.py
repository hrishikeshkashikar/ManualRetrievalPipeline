"""Password hashing and HMAC session tokens — stdlib only (offline-safe)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any


_PBKDF2_ROUNDS = 200_000
_TOKEN_TTL_SECONDS = 60 * 60 * 24  # 24h


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt_hex, hash_hex = stored.split("$", 2)
    except ValueError:
        return False
    if algo != "pbkdf2":
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(hash_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return hmac.compare_digest(dk, expected)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(payload: dict[str, Any], secret: str, ttl: int = _TOKEN_TTL_SECONDS) -> str:
    body = dict(payload)
    body["exp"] = int(time.time()) + ttl
    encoded = _b64url(json.dumps(body, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64url(sig)}"


def decode_token(token: str, secret: str) -> dict[str, Any] | None:
    try:
        encoded, sig_b64 = token.split(".", 1)
    except ValueError:
        return None
    expected = hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    try:
        given = _b64url_decode(sig_b64)
    except Exception:
        return None
    if not hmac.compare_digest(expected, given):
        return None
    try:
        payload = json.loads(_b64url_decode(encoded))
    except Exception:
        return None
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        return None
    return payload
