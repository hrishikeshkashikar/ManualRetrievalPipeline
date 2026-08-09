"""
Ingestion API routes.

Handles PDF upload, processing, indexing, and manual management.
"""

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File

from app.config import settings
from app.models.schemas import (
    DeleteManualResponse,
    IngestResponse,
    ManualInfo,
    ManualListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


def _reject_if_query_only() -> None:
    """Block write/ingest operations on query-only edge deployments."""
    if settings.query_only:
        raise HTTPException(
            status_code=403,
            detail=(
                "This instance is query-only. Ingest manuals on a stronger "
                "machine and mount the prebuilt data/ folder here."
            ),
        )


@router.post(
    "",
    response_model=IngestResponse,
    summary="Ingest a PDF manual",
    description=(
        "Upload a PDF machine manual for processing and indexing. "
        "The system will extract text, render pages, extract diagrams, "
        "generate captions for visual content, and index everything "
        "for retrieval."
    ),
)
async def ingest_manual(
    file: UploadFile = File(..., description="PDF file to ingest"),
) -> IngestResponse:
    """
    Ingest a PDF manual into the RAG pipeline.

    Steps:
    1. Validate and save the uploaded PDF
    2. Extract text and create chunks
    3. Render pages and extract images
    4. Generate captions for images via VLM
    5. Embed all chunks (text + captions)
    6. Store in ChromaDB
    """
    _reject_if_query_only()

    from app.main import app_state

    # Validate that we have a mounted data path
    if not app_state.current_mount_path:
        raise HTTPException(
            status_code=400,
            detail="UNMOUNTED"
        )

    if app_state.pdf_processor is None:
        raise HTTPException(
            status_code=503,
            detail="PDF processor is not available on this instance.",
        )

    start_time = time.time()

    # ── Validate file ──────────────────────────────────────────────────
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported. Please upload a .pdf file.",
        )

    # ── Save file ──────────────────────────────────────────────────────
    save_dir = settings.manual_store_dir
    save_dir.mkdir(parents=True, exist_ok=True)
    filepath = save_dir / file.filename

    try:
        content = await file.read()
        filepath.write_bytes(content)
        logger.info(f"Saved uploaded file: {filepath}")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save uploaded file: {e}",
        )

    # ── Generate manual ID ─────────────────────────────────────────────
    manual_id = app_state.pdf_processor.generate_manual_id(filepath)
    logger.info(f"Manual ID: {manual_id}")

    # Check if already ingested
    existing_manuals = app_state.vector_store.list_manuals()
    for m in existing_manuals:
        if m["manual_id"] == manual_id:
            elapsed = time.time() - start_time
            return IngestResponse(
                manual_id=manual_id,
                filename=file.filename,
                total_pages=0,
                text_chunks=m["total_chunks"],
                images_extracted=0,
                captions_generated=0,
                status="success",
                processing_time_seconds=round(elapsed, 2),
                message="Manual already indexed. Delete it first to re-ingest.",
            )

    # ── Process PDF ────────────────────────────────────────────────────
    try:
        text_chunks, images = app_state.pdf_processor.process_pdf(filepath, manual_id)
    except Exception as e:
        logger.error(f"PDF processing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process PDF: {e}",
        )

    total_pages = app_state.pdf_processor.get_page_count(filepath)
    images_extracted = len([i for i in images if i["type"] == "extracted_image"])

    # ── Generate captions for images via VLM ───────────────────────────
    caption_chunks = []
    try:
        caption_chunks = app_state.vision_captioner.process_images_for_manual(
            images=images,
            manual_id=manual_id,
            source_file=file.filename,
        )
    except Exception as e:
        logger.error(f"Caption generation failed (continuing without): {e}")
        # Continue without captions — text chunks are still valuable

    # ── Combine all chunks ─────────────────────────────────────────────
    all_chunks = text_chunks + caption_chunks

    if not all_chunks:
        elapsed = time.time() - start_time
        return IngestResponse(
            manual_id=manual_id,
            filename=file.filename,
            total_pages=total_pages,
            text_chunks=0,
            images_extracted=images_extracted,
            captions_generated=len(caption_chunks),
            status="failed",
            processing_time_seconds=round(elapsed, 2),
            message="No content could be extracted from the PDF.",
        )

    # ── Embed all chunks ───────────────────────────────────────────────
    try:
        contents = [chunk.content for chunk in all_chunks]
        embeddings = app_state.embedder.embed_documents(contents)
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate embeddings: {e}",
        )

    # ── Store in vector DB ─────────────────────────────────────────────
    try:
        stored_count = app_state.vector_store.add_documents(
            chunks=all_chunks,
            embeddings=embeddings,
        )
    except Exception as e:
        logger.error(f"Vector store insertion failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store in vector database: {e}",
        )

    elapsed = time.time() - start_time

    status = "success" if stored_count == len(all_chunks) else "partial"

    logger.info(
        f"Ingestion complete: {file.filename} → "
        f"{stored_count} chunks in {elapsed:.2f}s"
    )

    return IngestResponse(
        manual_id=manual_id,
        filename=file.filename,
        total_pages=total_pages,
        text_chunks=len(text_chunks),
        images_extracted=images_extracted,
        captions_generated=len(caption_chunks),
        status=status,
        processing_time_seconds=round(elapsed, 2),
        message=f"Successfully ingested {stored_count} chunks.",
    )


@router.get(
    "/manuals",
    response_model=ManualListResponse,
    summary="List indexed manuals",
    description="Get a list of all manuals that have been ingested.",
)
async def list_manuals() -> ManualListResponse:
    """List all currently indexed manuals with their stats."""
    from app.main import app_state

    # Validate that we have a mounted data path
    if not app_state.current_mount_path:
        raise HTTPException(
            status_code=400,
            detail="UNMOUNTED"
        )

    manuals_data = app_state.vector_store.list_manuals()

    manuals = [
        ManualInfo(
            manual_id=m["manual_id"],
            filename=m["filename"],
            total_chunks=m["total_chunks"],
            total_pages=0,  # Not tracked in current implementation
            indexed_at="",  # Not tracked in current implementation
        )
        for m in manuals_data
    ]

    return ManualListResponse(
        manuals=manuals,
        total_count=len(manuals),
    )


@router.delete(
    "/manuals/{manual_id}",
    response_model=DeleteManualResponse,
    summary="Delete an indexed manual",
    description="Remove a manual and all its indexed data.",
)
async def delete_manual(manual_id: str) -> DeleteManualResponse:
    """Delete a manual and all its associated data from the index."""
    _reject_if_query_only()

    from app.main import app_state

    # Validate that we have a mounted data path
    if not app_state.current_mount_path:
        raise HTTPException(
            status_code=400,
            detail="UNMOUNTED"
        )

    # Check if manual exists
    manuals = app_state.vector_store.list_manuals()
    found = any(m["manual_id"] == manual_id for m in manuals)

    if not found:
        raise HTTPException(
            status_code=404,
            detail=f"Manual with ID '{manual_id}' not found.",
        )

    success = app_state.vector_store.delete_manual(manual_id)

    # Also clean up stored images
    image_dir = settings.image_store_dir / manual_id
    if image_dir.exists():
        import shutil

        shutil.rmtree(image_dir, ignore_errors=True)
        logger.info(f"Cleaned up image directory: {image_dir}")

    return DeleteManualResponse(
        manual_id=manual_id,
        deleted=success,
        message=(
            "Manual deleted successfully."
            if success
            else "Manual deletion partially failed."
        ),
    )
