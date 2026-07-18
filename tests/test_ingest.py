"""
Tests for the ingestion pipeline.

Tests PDF processing, chunking, and the ingest API endpoint.
"""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    # Patch heavy model loading during tests
    with (
        patch("app.core.embedder.SentenceTransformer"),
        patch("app.core.reranker.CrossEncoder"),
    ):
        from app.main import app

        with TestClient(app) as c:
            yield c


class TestPDFProcessor:
    """Tests for the PDFProcessor component."""

    def test_chunk_text_basic(self):
        """Test basic text chunking."""
        from app.core.pdf_processor import PDFProcessor

        processor = PDFProcessor()
        # Override chunk size for testing
        processor.chunk_size = 50
        processor.chunk_overlap = 10

        text = "A" * 120  # 120 chars → should produce multiple chunks
        chunks = processor._chunk_text(text)

        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) > 0

    def test_chunk_text_empty(self):
        """Test chunking with empty text."""
        from app.core.pdf_processor import PDFProcessor

        processor = PDFProcessor()
        assert processor._chunk_text("") == []
        assert processor._chunk_text("   ") == []

    def test_chunk_text_with_section_header(self):
        """Test that section headers are prepended to chunks."""
        from app.core.pdf_processor import PDFProcessor

        processor = PDFProcessor()
        processor.chunk_size = 100
        processor.chunk_overlap = 10

        chunks = processor._chunk_text(
            "Some content here. " * 10,
            section_header="3.2 Troubleshooting",
        )

        assert len(chunks) > 0
        assert chunks[0].startswith("[3.2 Troubleshooting]")

    def test_detect_section_header_numbered(self):
        """Test detection of numbered section headers."""
        from app.core.pdf_processor import PDFProcessor

        processor = PDFProcessor()

        text = "3.2 Maintenance Procedures\nSome body text here."
        header = processor._detect_section_header(text)
        assert header is not None
        assert "3.2" in header
        assert "Maintenance" in header

    def test_detect_section_header_caps(self):
        """Test detection of all-caps headers."""
        from app.core.pdf_processor import PDFProcessor

        processor = PDFProcessor()

        text = "SAFETY WARNINGS\nAlways disconnect power before..."
        header = processor._detect_section_header(text)
        assert header == "SAFETY WARNINGS"

    def test_detect_section_header_none(self):
        """Test that no header is returned for regular text."""
        from app.core.pdf_processor import PDFProcessor

        processor = PDFProcessor()

        text = "This is just regular paragraph text without any header."
        header = processor._detect_section_header(text)
        assert header is None

    def test_generate_manual_id_deterministic(self, tmp_path):
        """Test that manual ID is deterministic for the same file."""
        from app.core.pdf_processor import PDFProcessor

        processor = PDFProcessor()

        # Create a temporary file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        id1 = processor.generate_manual_id(test_file)
        id2 = processor.generate_manual_id(test_file)
        assert id1 == id2
        assert len(id1) == 16


class TestIngestAPI:
    """Tests for the ingest API endpoints."""

    def test_ingest_rejects_non_pdf(self, client):
        """Test that non-PDF files are rejected."""
        response = client.post(
            "/ingest",
            files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    def test_list_manuals_empty(self, client):
        """Test listing manuals when none are indexed."""
        response = client.get("/ingest/manuals")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] >= 0

    def test_delete_nonexistent_manual(self, client):
        """Test deleting a manual that doesn't exist."""
        response = client.delete("/ingest/manuals/nonexistent123")
        assert response.status_code == 404
