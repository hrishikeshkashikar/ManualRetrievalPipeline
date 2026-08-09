"""
Tests for the 8GB edge / query-only profile.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def edge_env(monkeypatch):
    monkeypatch.setenv("QUERY_ONLY", "true")
    monkeypatch.setenv("ENABLE_RERANKER", "false")
    monkeypatch.setenv("OLLAMA_NUM_CTX", "8192")
    monkeypatch.setenv("MAX_GENERATION_IMAGES", "1")
    # Force settings reload
    from app.config import Settings

    return Settings()


def test_edge_settings_defaults(edge_env):
    assert edge_env.query_only is True
    assert edge_env.enable_reranker is False
    assert edge_env.ollama_num_ctx == 8192
    assert edge_env.max_generation_images == 1


def test_reranker_skip_returns_by_distance(monkeypatch):
    monkeypatch.setenv("ENABLE_RERANKER", "false")
    from app.config import Settings
    from app.core.reranker import Reranker
    from app.models.schemas import DocumentChunk, RetrievedChunk

    # Patch module settings used by Reranker
    import app.core.reranker as rr_mod
    import app.config as cfg_mod

    cfg = Settings()
    monkeypatch.setattr(cfg_mod, "settings", cfg)
    monkeypatch.setattr(rr_mod, "settings", cfg)

    chunks = [
        RetrievedChunk(
            chunk=DocumentChunk(
                chunk_id="a",
                content="far",
                content_type="text",
                source_file="m.pdf",
                manual_id="m1",
                page_number=1,
                chunk_index=0,
            ),
            distance=0.9,
        ),
        RetrievedChunk(
            chunk=DocumentChunk(
                chunk_id="b",
                content="near",
                content_type="text",
                source_file="m.pdf",
                manual_id="m1",
                page_number=2,
                chunk_index=0,
            ),
            distance=0.1,
        ),
    ]

    reranker = Reranker()
    reranker.load()
    assert not reranker.is_loaded

    result = reranker.rerank("q", chunks, top_n=1)
    assert len(result) == 1
    assert result[0].chunk.chunk_id == "b"


def test_generator_respects_zero_images(monkeypatch, tmp_path):
    monkeypatch.setenv("MAX_GENERATION_IMAGES", "0")
    from app.config import Settings
    import app.core.generator as gen_mod
    import app.config as cfg_mod

    cfg = Settings()
    monkeypatch.setattr(cfg_mod, "settings", cfg)
    monkeypatch.setattr(gen_mod, "settings", cfg)

    from app.core.generator import Generator
    from app.models.schemas import DocumentChunk, RetrievedChunk

    g = Generator()
    chunks = [
        RetrievedChunk(
            chunk=DocumentChunk(
                chunk_id="a",
                content="text",
                content_type="text",
                source_file="m.pdf",
                manual_id="m1",
                page_number=1,
                chunk_index=0,
                page_image_path=str(tmp_path / "page.png"),
            ),
            distance=0.1,
        )
    ]
    assert g._collect_images(chunks) == []


def test_query_only_blocks_ingest(monkeypatch):
    monkeypatch.setenv("QUERY_ONLY", "true")
    monkeypatch.setenv("ENABLE_RERANKER", "false")

    from app.config import Settings
    import app.config as cfg_mod

    cfg = Settings()
    monkeypatch.setattr(cfg_mod, "settings", cfg)

    with (
        patch("app.core.embedder.SentenceTransformer"),
        patch("app.core.reranker.CrossEncoder"),
    ):
        import importlib
        import app.main as main_mod
        import app.api.routes_ingest as ingest_mod

        monkeypatch.setattr(main_mod, "settings", cfg)
        monkeypatch.setattr(ingest_mod, "settings", cfg)

        importlib.reload(ingest_mod)
        importlib.reload(main_mod)
        # Re-apply after reload
        monkeypatch.setattr(main_mod, "settings", cfg)
        monkeypatch.setattr(ingest_mod, "settings", cfg)
        monkeypatch.setattr(cfg_mod, "settings", cfg)

        with TestClient(main_mod.app) as client:
            health = client.get("/health")
            assert health.status_code == 200
            body = health.json()
            assert body["query_only"] is True
            assert body["reranker_enabled"] is False

            resp = client.post(
                "/ingest",
                files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
            )
            assert resp.status_code == 403
            assert "query-only" in resp.json()["detail"].lower()
