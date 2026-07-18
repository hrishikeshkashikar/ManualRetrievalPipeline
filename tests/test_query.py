"""
Tests for the query pipeline.

Tests retrieval, reranking, and the query API endpoint.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models.schemas import (
    DocumentChunk,
    QueryRequest,
    RetrievedChunk,
)


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    with (
        patch("app.core.embedder.SentenceTransformer"),
        patch("app.core.reranker.CrossEncoder"),
    ):
        from app.main import app

        with TestClient(app) as c:
            yield c


@pytest.fixture
def sample_chunks():
    """Create sample document chunks for testing."""
    return [
        DocumentChunk(
            chunk_id="test_p1_c0",
            content="The motor may overheat if the cooling fan is blocked.",
            content_type="text",
            source_file="test_manual.pdf",
            manual_id="test123",
            page_number=1,
            chunk_index=0,
            section_header="3.1 Motor Troubleshooting",
            page_image_path="/data/images/test123/page_1.png",
        ),
        DocumentChunk(
            chunk_id="test_p2_c0",
            content="Check the oil level indicator on the front panel.",
            content_type="text",
            source_file="test_manual.pdf",
            manual_id="test123",
            page_number=2,
            chunk_index=0,
            section_header="4.2 Oil System",
            page_image_path="/data/images/test123/page_2.png",
        ),
    ]


@pytest.fixture
def sample_retrieved_chunks(sample_chunks):
    """Create sample retrieved chunks with distances."""
    return [
        RetrievedChunk(chunk=chunk, distance=0.1 * (i + 1))
        for i, chunk in enumerate(sample_chunks)
    ]


class TestQueryRequest:
    """Tests for the QueryRequest schema."""

    def test_valid_request(self):
        """Test creating a valid query request."""
        req = QueryRequest(query="Motor is overheating")
        assert req.query == "Motor is overheating"
        assert req.manual_filter is None
        assert req.top_k == 5

    def test_request_with_filter(self):
        """Test creating a request with manual filter."""
        req = QueryRequest(
            query="Motor overheating",
            manual_filter="manual123",
            top_k=3,
        )
        assert req.manual_filter == "manual123"
        assert req.top_k == 3

    def test_request_too_short(self):
        """Test that too-short queries are rejected."""
        with pytest.raises(Exception):
            QueryRequest(query="ab")  # min_length=3

    def test_request_top_k_bounds(self):
        """Test top_k boundary validation."""
        with pytest.raises(Exception):
            QueryRequest(query="test query", top_k=0)
        with pytest.raises(Exception):
            QueryRequest(query="test query", top_k=25)


class TestReranker:
    """Tests for the Reranker component."""

    def test_rerank_empty(self):
        """Test reranking with empty input."""
        from app.core.reranker import Reranker

        reranker = Reranker()
        result = reranker.rerank("test", [])
        assert result == []

    def test_rerank_returns_sorted(self, sample_retrieved_chunks):
        """Test that reranking returns results sorted by score."""
        from app.core.reranker import Reranker

        reranker = Reranker()
        # Mock the model
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.8, 0.3]
        reranker._model = mock_model

        result = reranker.rerank("motor overheating", sample_retrieved_chunks)

        assert len(result) <= 2
        # Verify sorted by score descending
        if len(result) > 1:
            assert result[0].rerank_score >= result[1].rerank_score


class TestQueryAPI:
    """Tests for the query API endpoints."""

    def test_query_no_manuals(self, client):
        """Test query when no manuals are indexed."""
        response = client.post(
            "/query",
            json={"query": "Motor is overheating"},
        )
        # Should return 400 since no manuals are indexed
        assert response.status_code == 400
        assert "No manuals" in response.json()["detail"]

    def test_query_validation(self, client):
        """Test query input validation."""
        response = client.post(
            "/query",
            json={"query": "ab"},  # Too short
        )
        assert response.status_code == 422  # Validation error


class TestDocumentChunk:
    """Tests for the DocumentChunk model."""

    def test_text_chunk(self):
        """Test creating a text chunk."""
        chunk = DocumentChunk(
            chunk_id="test_p1_c0",
            content="Test content",
            content_type="text",
            source_file="manual.pdf",
            manual_id="test123",
            page_number=1,
            chunk_index=0,
        )
        assert chunk.content_type == "text"
        assert chunk.image_path is None

    def test_caption_chunk(self):
        """Test creating an image caption chunk."""
        chunk = DocumentChunk(
            chunk_id="test_p1_cap_0",
            content="This diagram shows the wiring layout...",
            content_type="image_caption",
            source_file="manual.pdf",
            manual_id="test123",
            page_number=1,
            chunk_index=0,
            image_path="/data/images/test/page_1_img_0.png",
            page_image_path="/data/images/test/page_1.png",
        )
        assert chunk.content_type == "image_caption"
        assert chunk.image_path is not None
