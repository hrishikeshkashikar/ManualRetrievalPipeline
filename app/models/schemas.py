"""
Pydantic schemas for API request/response models.
"""

from pydantic import BaseModel, Field

# ── Ingest Schemas ──────────────────────────────────────────────────────────


class IngestResponse(BaseModel):
    """Response returned after ingesting a PDF manual."""

    manual_id: str = Field(..., description="Unique identifier for the ingested manual")
    filename: str = Field(..., description="Original filename of the uploaded PDF")
    total_pages: int = Field(..., description="Number of pages in the PDF")
    text_chunks: int = Field(..., description="Number of text chunks created")
    images_extracted: int = Field(
        ..., description="Number of images/diagrams extracted"
    )
    captions_generated: int = Field(
        ..., description="Number of image captions generated via VLM"
    )
    status: str = Field(
        ..., description="Processing status: success | partial | failed"
    )
    processing_time_seconds: float = Field(..., description="Total processing time")
    message: str = Field(
        default="", description="Additional information or error details"
    )


class ManualInfo(BaseModel):
    """Summary information about an indexed manual."""

    manual_id: str
    filename: str
    total_chunks: int
    total_pages: int
    indexed_at: str  # ISO timestamp


class ManualListResponse(BaseModel):
    """Response for listing all indexed manuals."""

    manuals: list[ManualInfo]
    total_count: int


class DeleteManualResponse(BaseModel):
    """Response after deleting a manual from the index."""

    manual_id: str
    deleted: bool
    message: str


# ── Query Schemas ───────────────────────────────────────────────────────────


class QueryRequest(BaseModel):
    """Request body for querying the RAG pipeline."""

    query: str = Field(
        ...,
        min_length=3,
        description="Problem description or question about the machine",
    )
    manual_filter: str | None = Field(
        default=None,
        description="Optional manual_id to restrict search to a specific manual",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of top results to use for answer generation",
    )


class SourceReference(BaseModel):
    """A reference to a source chunk used in the answer."""

    source_file: str = Field(..., description="Original PDF filename")
    page_number: int = Field(..., description="Page number in the PDF")
    section: str | None = Field(default=None, description="Section header if detected")
    content_type: str = Field(..., description="Type: text | image_caption")
    relevance_score: float = Field(..., description="Relevance score from reranking")
    snippet: str = Field(default="", description="Short excerpt of the matched content")
    page_image_path: str | None = Field(
        default=None,
        description="Relative path to the rendered page image",
    )


class QueryResponse(BaseModel):
    """Structured response from the RAG pipeline."""

    query: str = Field(..., description="The original query")
    answer: str = Field(..., description="Full structured answer from the VLM")
    possible_issues: list[str] = Field(
        default_factory=list,
        description="List of possible issues identified",
    )
    recommended_solutions: list[str] = Field(
        default_factory=list,
        description="List of recommended solutions",
    )
    safety_warnings: list[str] = Field(
        default_factory=list,
        description="Safety precautions from the manual",
    )
    sources: list[SourceReference] = Field(
        default_factory=list,
        description="Source references used to generate the answer",
    )
    processing_time_seconds: float = Field(..., description="Total processing time")


# ── Health Schemas ──────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """System health check response."""

    status: str = Field(
        ..., description="Overall status: healthy | degraded | unhealthy"
    )
    ollama_connected: bool = Field(..., description="Whether Ollama is reachable")
    ollama_model_available: bool = Field(
        ..., description="Whether the configured vision model is available in Ollama"
    )
    embedding_model_loaded: bool = Field(
        ..., description="Whether the embedding model is loaded"
    )
    reranker_loaded: bool = Field(
        ..., description="Whether the reranker model is loaded"
    )
    vector_store_ready: bool = Field(..., description="Whether ChromaDB is operational")
    manuals_indexed: int = Field(..., description="Number of manuals currently indexed")
    total_chunks: int = Field(..., description="Total chunks across all manuals")


# ── Internal Data Models ────────────────────────────────────────────────────


class DocumentChunk(BaseModel):
    """Internal representation of a processed document chunk."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    content: str = Field(..., description="Text content of the chunk")
    content_type: str = Field(..., description="Type: text | image_caption")
    source_file: str = Field(..., description="Original PDF filename")
    manual_id: str = Field(..., description="Manual identifier")
    page_number: int = Field(..., description="Page number (1-indexed)")
    chunk_index: int = Field(..., description="Chunk index within the page")
    section_header: str | None = Field(
        default=None, description="Detected section header"
    )
    image_path: str | None = Field(
        default=None,
        description="Path to the source image (for image_caption type)",
    )
    page_image_path: str | None = Field(
        default=None, description="Path to the rendered page image"
    )


class RetrievedChunk(BaseModel):
    """A chunk returned from vector search with its score."""

    chunk: DocumentChunk
    distance: float = Field(..., description="Vector distance (lower = more similar)")
    rerank_score: float | None = Field(
        default=None, description="Cross-encoder rerank score (higher = more relevant)"
    )
