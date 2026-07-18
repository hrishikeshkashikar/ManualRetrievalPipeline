"""
Machine Manual RAG Pipeline — FastAPI Application.

A fully local, offline RAG system for machine manual diagnosis.
Ingests PDF manuals (text + diagrams), and answers user questions
about machine problems with structured diagnostic responses.
"""

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.core.embedder import Embedder
from app.core.generator import Generator
from app.core.pdf_processor import PDFProcessor
from app.core.rag_pipeline import RAGPipeline
from app.core.reranker import Reranker
from app.core.vector_store import VectorStore
from app.core.vision_captioner import VisionCaptioner

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

    pdf_processor: PDFProcessor = field(default_factory=PDFProcessor)
    vision_captioner: VisionCaptioner = field(default_factory=VisionCaptioner)
    embedder: Embedder = field(default_factory=Embedder)
    vector_store: VectorStore = field(default_factory=VectorStore)
    reranker: Reranker = field(default_factory=Reranker)
    generator: Generator = field(default_factory=Generator)
    rag_pipeline: RAGPipeline | None = None
    current_mount_path: str | None = None


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
    - Load reranker model
    - Initialize vector store (if default exists)
    - Create RAG pipeline

    Shutdown:
    - Cleanup resources
    """
    global app_state

    logger.info("=" * 60)
    logger.info("  Machine Manual RAG Pipeline — Starting Up")
    logger.info("=" * 60)

    # Check if default data directory exists
    default_dir = settings.data_dir
    if default_dir.exists():
        try:
            settings.ensure_directories()
            logger.info(f"Auto-initializing default data path: {default_dir.resolve()}")
            app_state.vector_store.initialize()
            app_state.current_mount_path = str(default_dir.resolve())
            logger.info("Default vector store ready")
        except Exception as e:
            logger.warning(f"Failed to auto-initialize default data path: {e}")
    else:
        logger.info("No default data directory found on host. App starting in UNMOUNTED state.")

    # Load embedding model
    logger.info("Loading embedding model...")
    app_state.embedder.load()

    # Load reranker model
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
        logger.warning(
            f"Ollama model '{settings.ollama_vision_model}' not available. "
            "Ingestion will fail for image captioning. "
            "Run: ollama pull {settings.ollama_vision_model}"
        )

    logger.info("=" * 60)
    logger.info("  Pipeline ready — accepting requests")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("Shutting down Machine Manual RAG Pipeline...")


# ── FastAPI App ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Machine Manual RAG Pipeline",
    description=(
        "A fully local, offline RAG system for machine manual diagnosis. "
        "Upload PDF manuals, then ask questions about machine problems "
        "to get structured diagnostic responses with issue identification, "
        "solutions, and safety warnings — powered by multimodal AI that "
        "understands both text and diagrams."
    ),
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

app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(query_router)

# ── Dynamic Image Serving (serve page images from the mounted directory) ──

from fastapi.responses import FileResponse
from fastapi import HTTPException

@app.get("/data/images/{image_path:path}")
async def get_image(image_path: str):
    """Serve images dynamically from the currently mounted image store directory."""
    if not app_state.current_mount_path:
        raise HTTPException(status_code=400, detail="No data path is currently mounted.")
        
    full_path = settings.image_store_dir / image_path
    
    # Secure path checks (directory traversal guard)
    try:
        resolved = full_path.resolve()
        base_resolved = settings.image_store_dir.resolve()
        if not str(resolved).startswith(str(base_resolved)):
            raise HTTPException(status_code=403, detail="Access denied")
    except Exception:
        raise HTTPException(status_code=404, detail="Image not found")
        
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
        
    return FileResponse(resolved)


# ── Static Files (serve UI frontend directly from root) ─────────────────────

from fastapi.staticfiles import StaticFiles
from pathlib import Path

frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(frontend_dir), html=True),
        name="frontend",
    )
