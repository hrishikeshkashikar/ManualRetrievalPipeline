"""
Machine Manual RAG Pipeline — FastAPI Application.

A fully local, offline RAG system for machine manual diagnosis.
Ingests PDF manuals (text + diagrams), and answers user questions
about machine problems with structured diagnostic responses.
"""

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.auth.deps import AuthMiddleware

from app.config import settings
from app.core.embedder import Embedder
from app.core.generator import Generator
from app.core.rag_pipeline import RAGPipeline
from app.core.reranker import Reranker
from app.core.vector_store import VectorStore
from app.core.vision_captioner import VisionCaptioner

if TYPE_CHECKING:
    from app.core.pdf_processor import PDFProcessor

# ── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Application State ───────────────────────────────────────────────────────


@dataclass
class AppState:
    """
    Holds all initialized components.

    Created during application lifespan startup and available
    globally via the `app_state` module-level variable.
    """

    pdf_processor: "PDFProcessor | None" = None
    vision_captioner: VisionCaptioner = field(default_factory=VisionCaptioner)
    embedder: Embedder = field(default_factory=Embedder)
    vector_store: VectorStore = field(default_factory=VectorStore)
    reranker: Reranker = field(default_factory=Reranker)
    generator: Generator = field(default_factory=Generator)
    rag_pipeline: RAGPipeline | None = None
    current_mount_path: str | None = None  # user-facing path shown in UI
    resolved_mount_path: str | None = None  # actual path used for I/O


# Module-level state — populated during lifespan startup
app_state = AppState()


# ── Lifespan ────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Startup:
    - Ensure data directories exist (if default exists)
    - Load embedding model
    - Load reranker model (unless ENABLE_RERANKER=false)
    - Initialize vector store (if default exists)
    - Create RAG pipeline

    Shutdown:
    - Cleanup resources
    """
    global app_state

    logger.info("=" * 60)
    logger.info("  Machine Manual RAG Pipeline — Starting Up")
    if settings.query_only:
        logger.info("  Mode: QUERY-ONLY (edge) — ingest disabled")
    logger.info(
        "  Profile: num_ctx=%s max_images=%s reranker=%s",
        settings.ollama_num_ctx,
        settings.max_generation_images,
        settings.enable_reranker,
    )
    logger.info("=" * 60)

    # PDF processor only needed for ingest (lazy import — edge image omits PyMuPDF)
    if not settings.query_only:
        from app.core.pdf_processor import PDFProcessor

        app_state.pdf_processor = PDFProcessor()
    else:
        app_state.pdf_processor = None

    # Auto-mount default DATA_DIR when present (Docker: /app/data volume).
    # Catch BaseException too — Chroma rust bindings can raise PanicException.
    default_dir = settings.data_dir
    try:
        default_dir.mkdir(parents=True, exist_ok=True)
        settings.ensure_directories()
        logger.info("Auto-initializing default data path: %s", default_dir.resolve())
        app_state.vector_store.initialize(str(settings.chroma_persist_dir))
        app_state.current_mount_path = str(default_dir.resolve())
        app_state.resolved_mount_path = str(default_dir.resolve())
        logger.info("Default vector store ready")
    except BaseException as e:
        logger.warning("Failed to auto-initialize default data path: %s", e)
        logger.info("App starting in UNMOUNTED state — set a path from the UI.")
        app_state.vector_store = VectorStore()
        app_state.current_mount_path = None
        app_state.resolved_mount_path = None

    # Load embedding model
    logger.info("Loading embedding model...")
    app_state.embedder.load()

    # Load reranker model (skipped when disabled for edge RAM budget)
    logger.info("Loading reranker model...")
    app_state.reranker.load()

    # Create RAG pipeline (vector_store will read settings.chroma_persist_dir dynamically)
    app_state.rag_pipeline = RAGPipeline(
        embedder=app_state.embedder,
        vector_store=app_state.vector_store,
        reranker=app_state.reranker,
        generator=app_state.generator,
    )

    # Check Ollama
    if app_state.vision_captioner.is_available():
        logger.info(
            f"Ollama connected — model '{settings.ollama_vision_model}' available"
        )
    else:
        if settings.query_only:
            logger.warning(
                f"Ollama model '{settings.ollama_vision_model}' not available. "
                "Query generation will fail until the model is available."
            )
        else:
            logger.warning(
                f"Ollama model '{settings.ollama_vision_model}' not available. "
                "Ingestion will fail for image captioning. "
                f"Run: ollama pull {settings.ollama_vision_model}"
            )

    logger.info("=" * 60)
    logger.info("  Pipeline ready — accepting requests")
    logger.info("=" * 60)

    if settings.auth_enabled:
        from app.auth.store import get_store

        get_store()
        logger.info("Offline auth enabled — local users at %s", settings.auth_store_path)

    yield

    # Shutdown
    logger.info("Shutting down Machine Manual RAG Pipeline...")


# ── FastAPI App ─────────────────────────────────────────────────────────────

if settings.query_only:
    _description = (
        "A fully local, offline RAG system for machine manual diagnosis. "
        "Ask questions about machine problems to get structured diagnostic "
        "responses. This instance is query-only (no PDF ingest)."
    )
else:
    _description = (
        "A fully local, offline RAG system for machine manual diagnosis. "
        "Upload PDF manuals, then ask questions about machine problems "
        "to get structured diagnostic responses with issue identification, "
        "solutions, and safety warnings — powered by multimodal AI that "
        "understands both text and diagrams."
    )

app = FastAPI(
    title="Machine Manual RAG Pipeline",
    description=_description,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — permissive for local use, tighten for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ──────────────────────────────────────────────────────────────────

from app.api.routes_health import router as health_router
from app.api.routes_ingest import router as ingest_router
from app.api.routes_query import router as query_router
from app.auth.router import router as auth_router

app.add_middleware(AuthMiddleware)
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(ingest_router)  # list manuals always; write ops gated by query_only
app.include_router(query_router)

# ── Dynamic Image Serving (serve page images from the mounted directory) ──


@app.get("/data/images/{image_path:path}")
async def get_image(image_path: str):
    """Serve images dynamically from the currently mounted image store directory."""
    if not app_state.current_mount_path:
        raise HTTPException(status_code=400, detail="No data path is currently mounted.")

    full_path = settings.image_store_dir / image_path

    try:
        resolved = full_path.resolve()
        resolved.relative_to(settings.image_store_dir.resolve())
    except Exception:
        raise HTTPException(status_code=404, detail="Image not found") from None

    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(resolved)


# ── Static Files (serve UI frontend directly from root) ─────────────────────

frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(frontend_dir), html=True),
        name="frontend",
    )
