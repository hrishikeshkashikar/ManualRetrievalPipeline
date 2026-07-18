"""
Query API routes.

Handles user queries for machine problem diagnosis.
"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schemas import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Query"])


@router.post(
    "",
    response_model=QueryResponse,
    summary="Query the RAG pipeline",
    description=(
        "Submit a problem description or question about a machine. "
        "The system retrieves relevant manual pages, analyzes them "
        "(including diagrams), and returns a structured diagnosis "
        "with possible issues, solutions, and safety warnings."
    ),
)
async def query_rag(request: QueryRequest) -> QueryResponse:
    """
    Process a user query through the full RAG pipeline.

    1. Embeds the query
    2. Retrieves relevant chunks from indexed manuals
    3. Reranks for precision
    4. Sends context + images to VLM for diagnosis
    5. Returns structured response
    """
    from app.main import app_state

    # Validate that we have a mounted data path
    if not app_state.current_mount_path:
        raise HTTPException(
            status_code=400,
            detail="UNMOUNTED"
        )

    # Validate that we have indexed manuals
    total_chunks = app_state.vector_store.get_total_chunks()
    if total_chunks == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "No manuals have been indexed yet. "
                "Please ingest at least one manual using POST /ingest "
                "before querying."
            ),
        )

    try:
        response = await app_state.rag_pipeline.process_query(
            query=request.query,
            manual_filter=request.manual_filter,
            top_k=request.top_k,
        )
        return response

    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {e}",
        )


@router.post(
    "/stream",
    summary="Query with streaming response",
    description=(
        "Same as POST /query but streams the VLM's response "
        "token-by-token. Useful for real-time UI display."
    ),
)
async def query_rag_stream(request: QueryRequest):
    """
    Process a query with streaming response generation.

    Returns a text/event-stream response that yields tokens
    as the VLM generates them.
    """
    from app.main import app_state

    # Validate that we have a mounted data path
    if not app_state.current_mount_path:
        raise HTTPException(
            status_code=400,
            detail="UNMOUNTED"
        )

    total_chunks = app_state.vector_store.get_total_chunks()
    if total_chunks == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "No manuals have been indexed yet. "
                "Please ingest at least one manual using POST /ingest "
                "before querying."
            ),
        )

    async def generate():
        try:
            async for token in app_state.rag_pipeline.process_query_stream(
                query=request.query,
                manual_filter=request.manual_filter,
                top_k=request.top_k,
            ):
                yield token
        except Exception as e:
            logger.error(f"Streaming query failed: {e}", exc_info=True)
            yield f"\n\n[Error: {e}]"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )
