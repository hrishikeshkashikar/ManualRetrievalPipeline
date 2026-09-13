"""
RAG Pipeline orchestrator.

Ties together retrieval → reranking → generation into a single
high-level interface used by the API routes.
"""

import logging
import time

from app.core.embedder import Embedder
from app.core.generator import Generator
from app.core.reranker import Reranker
from app.core.vector_store import VectorStore
from app.models.schemas import QueryResponse, SourceReference
from app.utils.path_utils import to_web_image_path

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Orchestrates the full RAG pipeline:
    1. Embed the query
    2. Retrieve top-K candidates from vector store
    3. Rerank to top-N
    4. Generate a diagnostic answer using VLM
    """

    def __init__(
        self,
        embedder: Embedder,
        vector_store: VectorStore,
        reranker: Reranker,
        generator: Generator,
    ) -> None:
        self.embedder = embedder
        self.vector_store = vector_store
        self.reranker = reranker
        self.generator = generator

    async def process_query(
        self,
        query: str,
        manual_filter: str | None = None,
        top_k: int = 1,
    ) -> QueryResponse:
        """
        Process a user query through the full RAG pipeline.

        Args:
            query: Problem description or question from the user.
            manual_filter: Optional manual_id to restrict search scope.
            top_k: Number of top results after reranking.

        Returns:
            QueryResponse with structured diagnosis.
        """
        start_time = time.time()

        logger.info(f"Processing query: {query[:100]}...")

        # ── Step 1: Embed the query ────────────────────────────────────
        logger.debug("Step 1: Embedding query")
        query_embedding = self.embedder.embed_query(query)

        # ── Step 2: Retrieve candidates from vector store ──────────────
        logger.debug("Step 2: Retrieving candidates")
        from app.config import settings

        candidates = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=settings.top_k_retrieval,
            manual_filter=manual_filter,
        )

        if not candidates:
            elapsed = time.time() - start_time
            logger.warning("No candidates found for query")
            return QueryResponse(
                query=query,
                answer=(
                    "I couldn't find any relevant information in the "
                    "indexed manuals for your query. Please ensure that "
                    "the relevant manual has been ingested, or try "
                    "rephrasing your question."
                ),
                possible_issues=[],
                recommended_solutions=[],
                safety_warnings=[],
                sources=[],
                processing_time_seconds=round(elapsed, 2),
            )

        logger.debug(f"Retrieved {len(candidates)} candidates")

        # ── Step 3: Rerank to top-N ────────────────────────────────────
        logger.debug("Step 3: Reranking candidates")
        reranked = self.reranker.rerank(
            query=query,
            chunks=candidates,
            top_n=top_k,
        )
        logger.debug(f"Reranked to {len(reranked)} chunks")

        # ── Step 4: Generate answer with VLM ───────────────────────────
        logger.debug("Step 4: Generating answer")
        generated = await self.generator.generate(
            query=query,
            chunks=reranked,
        )

        # ── Step 5: Build response ─────────────────────────────────────
        sources = [
            SourceReference(
                source_file=rc.chunk.source_file,
                page_number=rc.chunk.page_number,
                section=rc.chunk.section_header,
                content_type=rc.chunk.content_type,
                relevance_score=round(rc.rerank_score or 0.0, 4),
                snippet=rc.chunk.content[:200],
                page_image_path=to_web_image_path(rc.chunk.page_image_path),
            )
            for rc in reranked
        ]

        elapsed = time.time() - start_time

        response = QueryResponse(
            query=query,
            answer=generated["answer"],
            possible_issues=generated["possible_issues"],
            recommended_solutions=generated["recommended_solutions"],
            safety_warnings=generated["safety_warnings"],
            sources=sources,
            processing_time_seconds=round(elapsed, 2),
        )

        logger.info(
            f"Query processed in {elapsed:.2f}s: "
            f"{len(sources)} sources, "
            f"{len(generated['possible_issues'])} issues identified"
        )

        return response

    async def process_query_stream(
        self,
        query: str,
        manual_filter: str | None = None,
        top_k: int = 1,
    ):
        """
        Process a query with SSE streaming response.

        Yields Server-Sent Events in this order:
        1. `event: sources` — JSON array of source references
        2. `event: token`   — one per LLM token
        3. `event: done`    — JSON with processing_time_seconds

        Skips the reranker for speed — retrieves top_k directly
        from the vector store using cosine similarity.

        Args:
            query: Problem description or question.
            manual_filter: Optional manual_id filter.
            top_k: Number of results to retrieve directly.

        Yields:
            SSE-formatted strings.
        """
        import json

        start_time = time.time()

        # ── Step 1: Embed the query ────────────────────────────────────
        query_embedding = self.embedder.embed_query(query)

        # ── Step 2: Retrieve top_k directly (skip reranker) ───────────
        candidates = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            manual_filter=manual_filter,
        )

        if not candidates:
            yield "event: sources\ndata: []\n\n"
            yield "event: token\ndata: No relevant information found in the indexed manuals.\n\n"
            elapsed = time.time() - start_time
            yield f"event: done\ndata: {{\"processing_time_seconds\": {round(elapsed, 2)}}}\n\n"
            return

        # ── Step 3: Emit sources immediately ──────────────────────────
        sources = [
            {
                "source_file": rc.chunk.source_file,
                "page_number": rc.chunk.page_number,
                "section": rc.chunk.section_header,
                "content_type": rc.chunk.content_type,
                "relevance_score": round(1.0 - rc.distance, 4),  # cosine distance → similarity
                "snippet": rc.chunk.content[:200],
                "page_image_path": to_web_image_path(rc.chunk.page_image_path),
            }
            for rc in candidates
        ]

        sources_json = json.dumps(sources, ensure_ascii=False)
        yield f"event: sources\ndata: {sources_json}\n\n"

        # ── Step 4: Stream LLM tokens ─────────────────────────────────
        async for token in self.generator.generate_stream(
            query=query,
            chunks=candidates,
        ):
            # Each token is a single SSE event. Newlines in the token
            # are handled by splitting into multiple data: lines per SSE spec.
            data_lines = token.split("\n")
            sse_data = "\ndata: ".join(data_lines)
            yield f"event: token\ndata: {sse_data}\n\n"

        # ── Step 5: Done event with timing ────────────────────────────
        elapsed = time.time() - start_time
        logger.info(
            f"Stream query processed in {elapsed:.2f}s: "
            f"{len(sources)} sources"
        )
        yield f"event: done\ndata: {{\"processing_time_seconds\": {round(elapsed, 2)}}}\n\n"

