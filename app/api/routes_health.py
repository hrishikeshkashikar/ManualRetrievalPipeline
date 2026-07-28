"""
Health check and dynamic data-mount API routes.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    BrowseResponse,
    HealthResponse,
    MountRequest,
    MountResponse,
)
from app.utils.path_utils import list_directory, resolve_host_path, running_in_docker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/config/browse",
    response_model=BrowseResponse,
    summary="Browse host folders visible to the container",
    description=(
        "List directories under host roots mirrored into Docker "
        "(/Users, /Volumes, /home, /media, /mnt). Used by the UI folder picker."
    ),
)
async def browse_host_path(
    path: str = Query(default="/", description="Host path to list"),
) -> BrowseResponse:
    try:
        data = list_directory(path)
        return BrowseResponse(**data)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        logger.error("Browse failed for %s: %s", path, e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e


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
        return MountResponse(
            status="mounted",
            path=app_state.current_mount_path,
            message="Data directory is mounted.",
        )
    return MountResponse(status="unmounted", path=None, message="No data directory mounted.")


@router.post(
    "/config/mount",
    response_model=MountResponse,
    summary="Dynamically mount a data directory",
    description=(
        "Set the absolute path of the data directory and initialize ChromaDB. "
        "In Docker, host paths under /Users, /Volumes, /home, /media, /mnt "
        "are mapped via /host/... bind mounts."
    ),
)
async def mount_data_directory(request: MountRequest) -> MountResponse:
    """Mount a new data directory and re-initialize storage paths and ChromaDB."""
    from app.config import settings
    from app.main import app_state

    path_str = request.path.strip()
    if not path_str:
        raise HTTPException(status_code=400, detail="Path cannot be empty")

    try:
        path = resolve_host_path(path_str)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        path.mkdir(parents=True, exist_ok=True)

        # Update settings paths to the resolved (container-visible) directory
        settings.update_paths(path)

        # Re-initialize vector store against the new chroma_db folder
        app_state.vector_store.initialize(str(settings.chroma_persist_dir))

        # Keep the user-facing path (what they typed) for display
        app_state.current_mount_path = path_str
        app_state.resolved_mount_path = str(path.resolve())

        logger.info(
            "Dynamic mount success: display=%s resolved=%s docker=%s",
            app_state.current_mount_path,
            app_state.resolved_mount_path,
            running_in_docker(),
        )
        return MountResponse(
            status="mounted",
            path=app_state.current_mount_path,
            message=(
                "Data directory mounted and vector store initialized successfully."
                + (f" (container path: {app_state.resolved_mount_path})" if running_in_docker() else "")
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to mount directory %s: %s", path_str, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mount and initialize directory: {e}",
        ) from e


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health check",
    description="Check the status of all system components.",
)
async def health_check() -> HealthResponse:
    """
    Perform a comprehensive health check of all system components.
    """
    from app.main import app_state

    ollama_connected = False
    ollama_model_available = False
    try:
        ollama_connected = True
        ollama_model_available = app_state.vision_captioner.is_available()
    except Exception as e:
        logger.warning("Ollama health check failed: %s", e)

    embedding_loaded = app_state.embedder.is_loaded
    reranker_loaded = app_state.reranker.is_loaded
    vector_store_ready = app_state.vector_store.is_ready

    manuals_indexed = 0
    total_chunks = 0
    if vector_store_ready:
        try:
            manuals = app_state.vector_store.list_manuals()
            manuals_indexed = len(manuals)
            total_chunks = app_state.vector_store.get_total_chunks()
        except Exception as e:
            logger.warning("Failed to get manual stats: %s", e)

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
