"""JSON user store on disk — works fully offline, independent of the KB mount."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.auth.security import hash_password

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_store: "UserStore | None" = None


class UserStore:
    def __init__(self, path: Path, secret: str, seed_username: str, seed_password: str):
        self.path = Path(path)
        self._secret = secret
        self._seed_username = (seed_username or "admin").strip().lower()
        self._seed_password = seed_password or "admin"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure()

    @property
    def secret(self) -> str:
        return self._secret

    def _empty_doc(self) -> dict[str, Any]:
        return {"secret": self._secret, "users": []}

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty_doc()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Corrupt auth store at %s — recreating", self.path)
            return self._empty_doc()
        if not isinstance(data, dict):
            return self._empty_doc()
        data.setdefault("users", [])
        if data.get("secret"):
            self._secret = str(data["secret"])
        else:
            data["secret"] = self._secret
        return data

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _ensure(self) -> None:
        with _lock:
            data = self._read()
            if not data.get("users"):
                data["users"].append(self._make_user(self._seed_username, self._seed_password, "admin"))
                logger.info("Seeded offline admin user '%s'", self._seed_username)
            data["secret"] = self._secret
            self._write(data)

    def _make_user(self, username: str, password: str, role: str) -> dict[str, Any]:
        return {
            "id": uuid.uuid4().hex,
            "username": username.strip().lower(),
            "password_hash": hash_password(password),
            "role": role if role in ("admin", "user") else "user",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_public(self) -> list[dict[str, Any]]:
        with _lock:
            return [
                {"id": u["id"], "username": u["username"], "role": u.get("role", "user")}
                for u in self._read()["users"]
            ]

    def count(self) -> int:
        with _lock:
            return len(self._read()["users"])

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        key = username.strip().lower()
        with _lock:
            for user in self._read()["users"]:
                if user.get("username") == key:
                    return user
        return None

    def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        with _lock:
            for user in self._read()["users"]:
                if user.get("id") == user_id:
                    return user
        return None

    def create(self, username: str, password: str, role: str = "user") -> dict[str, Any]:
        key = username.strip().lower()
        if not key or not password:
            raise ValueError("Username and password are required")
        if len(password) < 4:
            raise ValueError("Password must be at least 4 characters")
        with _lock:
            data = self._read()
            if any(u.get("username") == key for u in data["users"]):
                raise ValueError("Username already exists")
            user = self._make_user(key, password, role)
            data["users"].append(user)
            self._write(data)
            return user


def get_store() -> UserStore:
    from app.config import settings

    global _store
    path = Path(settings.auth_store_path)
    if _store is None or _store.path != path:
        _store = UserStore(
            path=path,
            secret=settings.auth_secret,
            seed_username=settings.auth_username,
            seed_password=settings.auth_password,
        )
    return _store


def reset_store() -> None:
    global _store
    _store = None
