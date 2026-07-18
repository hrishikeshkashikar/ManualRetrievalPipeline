"""
Embedding module.

Wraps sentence-transformers for generating text embeddings.
Uses BGE models with appropriate query prefixes for optimal retrieval.
"""

import logging

from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

# BGE models require a specific query prefix for best retrieval results.
# See: https://huggingface.co/BAAI/bge-base-en-v1.5
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder:
    """
    Text embedding model wrapper.

    Loads a sentence-transformers model and provides methods for
    embedding documents and queries. Designed to be initialized once
    at application startup and reused.
    """

    def __init__(self) -> None:
        self.model_name = settings.embedding_model_name
        self.batch_size = settings.embedding_batch_size
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None

    def load(self) -> None:
        """
        Load the embedding model into memory.

        Call this during application startup (FastAPI lifespan).
        """
        logger.info(f"Loading embedding model: {self.model_name}")
        self._model = SentenceTransformer(self.model_name)
        # Determine the embedding dimension
        self._dimension = self._model.get_sentence_embedding_dimension()
        logger.info(f"Embedding model loaded. Dimension: {self._dimension}")

    @property
    def model(self) -> SentenceTransformer:
        """Get the loaded model, raising if not initialized."""
        if self._model is None:
            raise RuntimeError("Embedding model not loaded. Call load() first.")
        return self._model

    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        if self._dimension is None:
            raise RuntimeError("Embedding model not loaded. Call load() first.")
        return self._dimension

    @property
    def is_loaded(self) -> bool:
        """Check if the model is loaded."""
        return self._model is not None

    def _is_bge_model(self) -> bool:
        """Check if the current model is a BGE model (needs query prefix)."""
        return "bge" in self.model_name.lower()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of document texts.

        Documents do NOT get the BGE query prefix — they are stored as-is.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each a list of floats).
        """
        if not texts:
            return []

        logger.debug(f"Embedding {len(texts)} documents")
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=len(texts) > 100,
            normalize_embeddings=True,  # Cosine similarity via dot product
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """
        Generate an embedding for a single query.

        If using a BGE model, the query prefix is automatically prepended
        for optimal retrieval performance.

        Args:
            query: The query text to embed.

        Returns:
            Embedding vector as a list of floats.
        """
        if self._is_bge_model():
            query = f"{BGE_QUERY_PREFIX}{query}"

        embedding = self.model.encode(
            query,
            normalize_embeddings=True,
        )
        return embedding.tolist()
