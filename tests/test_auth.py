"""Offline local-user auth tests."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.store import reset_store


@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.auth_enabled", True)
    monkeypatch.setattr("app.config.settings.auth_store_path", tmp_path / "users.json")
    monkeypatch.setattr("app.config.settings.auth_username", "admin")
    monkeypatch.setattr("app.config.settings.auth_password", "secret")
    monkeypatch.setattr("app.config.settings.auth_allow_register", True)
    reset_store()

    with (
        patch("app.core.embedder.SentenceTransformer"),
        patch("app.core.reranker.CrossEncoder"),
    ):
        from app.main import app

        with TestClient(app) as client:
            yield client
    reset_store()


def test_auth_status_public(auth_client):
    res = auth_client.get("/auth/status")
    assert res.status_code == 200
    body = res.json()
    assert body["enabled"] is True
    assert body["has_users"] is True


def test_health_stays_public(auth_client):
    res = auth_client.get("/health")
    assert res.status_code == 200
    assert res.json()["auth_enabled"] is True


def test_query_requires_login(auth_client):
    res = auth_client.post("/query", json={"query": "motor overheating now"})
    assert res.status_code == 401


def test_login_and_me(auth_client):
    bad = auth_client.post("/auth/login", json={"username": "admin", "password": "nope"})
    assert bad.status_code == 401

    ok = auth_client.post("/auth/login", json={"username": "admin", "password": "secret"})
    assert ok.status_code == 200
    token = ok.json()["access_token"]
    assert token
    assert ok.json()["user"]["username"] == "admin"

    me = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "admin"


def test_register_new_user(auth_client):
    admin = auth_client.post("/auth/login", json={"username": "admin", "password": "secret"})
    token = admin.json()["access_token"]
    created = auth_client.post(
        "/auth/register",
        json={"username": "tech", "password": "pass"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 200
    assert created.json()["user"]["username"] == "tech"

    login = auth_client.post("/auth/login", json={"username": "tech", "password": "pass"})
    assert login.status_code == 200
