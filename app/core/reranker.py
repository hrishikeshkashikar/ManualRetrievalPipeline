"""
Reranker module.

Uses a cross-encoder model to rerank retrieved chunks for higher precision.
The bi-encoder retrieval casts a wide net; the cross-encoder picks the best.
"""

import logging

from sentence_transformers import CrossEncoder

from app.config import settings
from app.models.schemas import RetrievedChunk

logger = logging.getLogger(__name__)


class Reranker:
    """
    Cross-encoder reranker for improving retrieval precision.

    Takes a query and a list of retrieved chunks, scores each
    (query, chunk) pair, and returns the top-N most relevant.
    """

    def __init__(self) -> None:
        self.model_name = settings.reranker_model_name
        self._model: CrossEncoder | None = None

    def load(self) -> None:
        """
        Load the cross-encoder model into memory.

        Call this during application startup (FastAPI lifespan).
        """
        logger.info(f"Loading reranker model: {self.model_name}")
        self._model = CrossEncoder(self.model_name)
        logger.info("Reranker model loaded successfully")

    @property
    def model(self) -> CrossEncoder:
        """Get the loaded model, raising if not initialized."""
        if self._model is None:
            raise RuntimeError("Reranker model not loaded. Call load() first.")
        return self._model

    @property
    def is_loaded(self) -> bool:
        """Check if the model is loaded."""
        return self._model is not None

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int | None = None,
    ) -> list[RetrievedChunk]:
        """
        Rerank retrieved chunks by relevance to the query.

        Args:
            query: The user's query text.
            chunks: List of RetrievedChunk from vector search.
            top_n: Number of top results to return.
                   Defaults to settings.top_k_rerank.

        Returns:
            Reranked list of RetrievedChunk, sorted by relevance
            (highest score first), trimmed to top_n.
        """
        if not chunks:
            return []

        top_n = top_n or settings.top_k_rerank

        # Create (query, document) pairs for the cross-encoder
        pairs = [(query, chunk.chunk.content) for chunk in chunks]

        # Score all pairs
        scores = self.model.predict(pairs)

        # Attach scores to chunks
        for chunk, score in zip(chunks, scores):
            chunk.rerank_score = float(score)

        # Sort by rerank score (descending — higher is more relevant)
        reranked = sorted(chunks, key=lambda c: c.rerank_score or 0.0, reverse=True)

        # Trim to top_n
        result = reranked[:top_n]

        logger.debug(
            f"Reranked {len(chunks)} chunks → top {len(result)}. "
            f"Score range: {result[-1].rerank_score:.3f} to "
            f"{result[0].rerank_score:.3f}"
            if result
            else "No results after reranking"
        )

        return result
