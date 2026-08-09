"""
Configuration for the Machine Manual RAG Pipeline.

All settings are loaded from environment variables (or .env file),
with sensible defaults for local development.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Ollama ──────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_vision_model: str = "qwen2.5vl:3b"
    ollama_request_timeout: float = 300.0  # seconds – vision inference can be slow
    ollama_num_ctx: int = 32768  # context window size for Ollama models

    # ── Embedding Model (sentence-transformers) ────────────────────────
    embedding_model_name: str = "BAAI/bge-base-en-v1.5"
    embedding_batch_size: int = 32

    # ── Reranker Model (cross-encoder) ─────────────────────────────────
    reranker_model_name: str = "BAAI/bge-reranker-v2-m3"
    enable_reranker: bool = True  # set False on 8GB edge to save RAM

    # ── Edge / query-only profile ──────────────────────────────────────
    # When True: no ingest/delete, skip heavy ingest components at startup.
    # Pair with lower ollama_num_ctx + max_generation_images via env.
    query_only: bool = False

    # ── Storage Paths ──────────────────────────────────────────────────
    data_dir: Path = Path("./data")
    chroma_persist_dir: Path = Path("./data/chroma_db")
    image_store_dir: Path = Path("./data/images")
    manual_store_dir: Path = Path("./data/manuals")

    # ── Chunking ───────────────────────────────────────────────────────
    chunk_size: int = 512  # characters (not tokens, for simplicity)
    chunk_overlap: int = 64

    # ── Retrieval ──────────────────────────────────────────────────────
    top_k_retrieval: int = 15  # initial broad retrieval from vector store
    top_k_rerank: int = 5  # after reranking – sent to LLM

    # ── Image Processing ───────────────────────────────────────────────
    max_image_resolution: int = 1024  # max width/height in pixels for VLM input
    page_render_dpi: int = 300  # DPI for rendering PDF pages to images
    max_generation_images: int = 4  # images attached to VLM generate calls

    # ── Server ─────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    def ensure_directories(self) -> None:
        """Create all required data directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.image_store_dir.mkdir(parents=True, exist_ok=True)
        self.manual_store_dir.mkdir(parents=True, exist_ok=True)

    def update_paths(self, base_path: Path) -> None:
        """Update all dependent storage paths based on a new base path."""
        self.data_dir = base_path
        self.chroma_persist_dir = base_path / "chroma_db"
        self.image_store_dir = base_path / "images"
        self.manual_store_dir = base_path / "manuals"
        self.ensure_directories()


# Singleton settings instance
settings = Settings()
