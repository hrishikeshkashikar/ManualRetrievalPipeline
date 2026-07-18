"""
Health check API routes.
"""

import logging

from fastapi import APIRouter, Depends

from app.models.schemas import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health check",
    description="Check the status of all system components.",
)
async def health_check() -> HealthResponse:
    """
    Perform a comprehensive health check of all system components.

    Checks:
    - Ollama connectivity and model availability
    - Embedding model loaded status
    - Reranker model loaded status
    - Vector store readiness
    - Indexed manual statistics
    """
    from app.main import app_state

    # Check Ollama
    ollama_connected = False
    ollama_model_available = False
    try:
        ollama_connected = True
        ollama_model_available = app_state.vision_captioner.is_available()
    except Exception as e:
        logger.warning(f"Ollama health check failed: {e}")

    # Check embedding model
    embedding_loaded = app_state.embedder.is_loaded

    # Check reranker
    reranker_loaded = app_state.reranker.is_loaded

    # Check vector store
    vector_store_ready = app_state.vector_store.is_ready

    # Get manual stats
    manuals_indexed = 0
    total_chunks = 0
    if vector_store_ready:
        try:
            manuals = app_state.vector_store.list_manuals()
            manuals_indexed = len(manuals)
            total_chunks = app_state.vector_store.get_total_chunks()
        except Exception as e:
            logger.warning(f"Failed to get manual stats: {e}")

    # Determine overall status
    all_ok = all(
        [
            ollama_connected,
            ollama_model_available,
            embedding_loaded,
            reranker_loaded,
            vector_store_ready,
        ]
    )
    if all_ok:
        status = "healthy"
    elif vector_store_ready and embedding_loaded:
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        ollama_connected=ollama_connected,
        ollama_model_available=ollama_model_available,
        embedding_model_loaded=embedding_loaded,
        reranker_loaded=reranker_loaded,
        vector_store_ready=vector_store_ready,
        manuals_indexed=manuals_indexed,
        total_chunks=total_chunks,
    )
