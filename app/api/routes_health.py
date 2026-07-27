"""
Health check API routes.
"""

import logging

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import HealthResponse, MountRequest, MountResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/config/mount",
    response_model=MountResponse,
    summary="Get current data mount configuration",
    description="Check if a data directory is currently mounted and retrieve its path.",
)
async def get_mount_config() -> MountResponse:
    """Get the currently active mounted data path status."""
    from app.main import app_state
    if app_state.current_mount_path:
        return MountResponse(status="mounted", path=app_state.current_mount_path)
    return MountResponse(status="unmounted", path=None)


@router.post(
    "/config/mount",
    response_model=MountResponse,
    summary="Dynamically mount a data directory",
    description="Set the absolute path of the data directory and initialize system components.",
)
async def mount_data_directory(request: MountRequest) -> MountResponse:
    """Mount a new data directory and re-initialize storage paths and ChromaDB."""
    from app.main import app_state
    from app.config import settings

    path_str = request.path.strip()
    if not path_str:
        raise HTTPException(status_code=400, detail="Path cannot be empty")

    import os
    is_docker = os.path.exists("/.dockerenv") or os.environ.get("HF_HUB_OFFLINE") == "1"

    path = Path(path_str)

    if is_docker and not path.exists():
        # Try to resolve it via /host mount translation (e.g. /Users/... -> /host/Users/...)
        host_prefixes = ("/Users", "/Volumes", "/home", "/media", "/mnt")
        if path_str.startswith(host_prefixes):
            host_translated = Path("/host") / path_str.lstrip("/")
            if host_translated.exists():
                path = host_translated
                logger.info(f"Host path translated inside container: {path_str} -> {path}")
            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Host path '{path_str}' was mapped to '{host_translated}' inside the container, "
                        "but this directory does not exist. Please check if the directory exists on your host machine."
                    )
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Path '{path_str}' does not exist inside the container. "
                    "Docker containers cannot access host paths directly. "
                    "To use a host path, it must be located within one of: /Users, /Volumes, /home, /media, /mnt."
                )
            )

    try:
        # Create directories on target path if they don't exist
        path.mkdir(parents=True, exist_ok=True)
        
        # Update settings paths
        settings.update_paths(path)
        
        # Re-initialize vector store with the new Chroma DB folder
        app_state.vector_store.initialize(str(settings.chroma_persist_dir))
        
        # Update app mount state
        app_state.current_mount_path = path_str
        
        logger.info(f"Dynamic mount success: {app_state.current_mount_path} (mapped to internal path: {path})")
        return MountResponse(
            status="mounted",
            path=app_state.current_mount_path,
            message="Data directory mounted and vector store initialized successfully."
        )
    except Exception as e:
        logger.error(f"Failed to mount directory {path_str}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mount and initialize directory: {e}"
        )


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
