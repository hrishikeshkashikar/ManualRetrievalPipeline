================================================================================
          MACHINE MANUAL RAG PIPELINE — TECHNICAL DOCUMENTATION
================================================================================
Author: AI Systems Engineering / Machine Manual RAG Team
Version: 1.0.0
Architecture Type: Fully Local, Offline Multimodal Retrieval-Augmented Generation (RAG)
Target Deployment: Edge Servers, On-Premises Maintenance Workstations, Docker

--------------------------------------------------------------------------------
TABLE OF CONTENTS
--------------------------------------------------------------------------------
1. EXECUTIVE SUMMARY & OVERVIEW
2. SYSTEM ARCHITECTURE & DATA FLOW
3. TECHNOLOGY STACK & MODEL SPECIFICATIONS
4. DETAILED PIPELINE SUBSYSTEMS
   4.1 PDF Ingestion & Document Processing Module
   4.2 Vision-Language Captioning Module (VLM)
   4.3 Dense Text Embedding Module
   4.4 Vector Storage & Indexing Engine (ChromaDB)
   4.5 Cross-Encoder Reranking Engine
   4.6 Diagnostic Generation Engine (Rest & SSE Streaming)
5. API ROUTE SPECIFICATIONS & ENDPOINTS
6. FRONTEND USER INTERFACE & INTEGRATION
7. CONFIGURATION & ENVIRONMENT VARIABLES
8. DEPLOYMENT & OPERATION GUIDE (Local vs. Docker)
9. KNOWN TROUBLESHOOTING & EDGE CASES

================================================================================
1. EXECUTIVE SUMMARY & OVERVIEW
================================================================================
The Machine Manual RAG Pipeline is a fully offline, local multimodal diagnostic 
assistance application. It enables maintenance technicians and engineers to 
upload complex industrial machinery manuals (PDF format)—containing technical text, 
schematics, electrical wiring diagrams, exploded assembly drawings, and safety 
tables—and query them in natural language.

Key Features & System Capabilities:
• 100% Air-Gapped & Local: Operates without internet connectivity after model initial load.
• Multimodal Ingestion: Converts visual content (diagrams, tables, flowcharts) into searchable text captions using local Vision Language Models (VLMs).
• Two-Stage Retrieval Strategy: Combines dense vector similarity search (Bi-Encoder) with high-precision re-ranking (Cross-Encoder).
• Structured Diagnostic Output: Generates structured troubleshooting steps, probable root causes, actionable solutions, and highlighted safety warnings.
• Real-time SSE Token Streaming: Offers token-by-token streaming over Server-Sent Events (SSE) for interactive chat UI responsiveness.
• Exact Source Attribution: Points technicians directly to exact PDF filenames, page numbers, detected section headers, and page image previews.

================================================================================
2. SYSTEM ARCHITECTURE & DATA FLOW
================================================================================

[ PDF MANUAL UPLOAD ]
         │
         ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PDF INGESTION & EXTRACTOR (PyMuPDF)                                    │
│ ├── 1. Text Extraction & Sentence-Aware Chunking (512 char / 64 overlap) │
│ ├── 2. High-Res Page Rendering (300 DPI PNG)                           │
│ └── 3. Embedded Image/Diagram Extraction (>50x50 px)                  │
└────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────────────┐
│ VISION-LANGUAGE CAPTIONER (Ollama: qwen2.5vl / llama3.2-vision)        │
│ └── Generates detailed text descriptions of diagrams, schematics, etc. │
└────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────────────┐
│ EMBEDDING ENGINE (SentenceTransformers: BAAI/bge-base-en-v1.5)         │
│ └── Converts text & image captions into 768-dim dense vector embeddings │
└────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────────────┐
│ VECTOR DATABASE (ChromaDB)                                             │
│ ├── Collection per manual (manual_{manual_id})                         │
│ └── Unified cross-manual collection (all_manuals)                      │
└────────────────────────────────────────────────────────────────────────┘

                               ──── * ────

[ TECHNICIAN QUERY ]
         │
         ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: BGE QUERY EMBEDDER                                            │
│ └── Appends BGE prefix -> Generates 768-dim Query Vector              │
└────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: BI-ENCODER DENSE SEARCH (ChromaDB Cosine HNSW)                │
│ └── Broad retrieval of Top-15 candidate chunks                         │
└────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: CROSS-ENCODER RERANKING (BAAI/bge-reranker-v2-m3)             │
│ └── Scores (query, chunk) pairs -> Filters to Top-5 highest relevance  │
└────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: VLM CONTEXT ASSEMBLY & DIAGNOSTIC GENERATION (Ollama)          │
│ ├── Assembles text context excerpts + source metadata                  │
│ ├── Attaches up to 4 high-res page / diagram image payloads             │
│ └── Generates structured JSON (REST) or formatted Markdown (SSE Stream) │
└────────────────────────────────────────────────────────────────────────┘

================================================================================
3. TECHNOLOGY STACK & MODEL SPECIFICATIONS
================================================================================
• Backend Framework: FastAPI (v0.115.0+), Uvicorn ASGI Server
• Programming Language: Python 3.11 / 3.12
• PDF & Document Processing: PyMuPDF (fitz v1.24.0+), Pillow (PIL v10.0.0+)
• Dense Embedding Model: BAAI/bge-base-en-v1.5 (SentenceTransformers v3.0.0+)
  - Dimension: 768 float32 vector
  - Query Prefix: "Represent this sentence for searching relevant passages: "
• Reranking Model: BAAI/bge-reranker-v2-m3 (CrossEncoder)
  - Scoring: Pairwise query-document cross-attention scoring
• Vector Database: ChromaDB (v0.5.0+) with persistent HNSW Cosine Index
• Local LLM/VLM Inference Engine: Ollama (v0.4.0+)
  - Supported Vision Models: qwen2.5vl:3b, qwen2.5vl:7b, llama3.2-vision:11b
  - Context Window: 32,768 tokens (configurable)
• Frontend: Vanilla HTML5, CSS3, JavaScript ES6+ (Native EventSource for SSE streaming)
• Containerization: Docker & Docker Compose (Base: python:3.11-slim + ollama/ollama:latest)

================================================================================
4. DETAILED PIPELINE SUBSYSTEMS
================================================================================

--------------------------------------------------------------------------------
4.1 PDF Ingestion & Document Processing Module (`app/core/pdf_processor.py`)
--------------------------------------------------------------------------------
1. Manual ID Generation: Calculates a deterministic 16-character SHA-256 hash of 
   the input PDF binary to prevent duplicate indexing.
2. Text Extraction & Section Header Detection:
   - Scans lines looking for section numbering (e.g., "1.2 Maintenance"), 
     keyword titles ("Chapter 3: Lubrication"), or uppercase headers.
   - Prepends detected section headers to text chunks for context retention.
3. Sentence-Aware Chunking:
   - Default Chunk Size: 512 characters
   - Chunk Overlap: 64 characters
   - Dynamically searches for sentence boundaries (. , ; newline) near chunk 
     limits to preserve grammatical integrity.
4. Page Rendering & Image Extraction:
   - Renders each page as a 300 DPI PNG file (`./data/images/{manual_id}/page_{page_num}.png`).
   - Extracts embedded vector/raster images with dimensions >= 50x50 pixels.

--------------------------------------------------------------------------------
4.2 Vision-Language Captioning Module (`app/core/vision_captioner.py`)
--------------------------------------------------------------------------------
Diagrams and page renders are sent to Ollama's vision model to convert visual data 
into detailed text captions:
• Prompts instruct the model to describe component names, part numbers, wiring 
  paths, color codes, warning labels, and measurement specifications.
• Generated captions are wrapped into `DocumentChunk` objects (`content_type="image_caption"`) 
  and embedded alongside pure text chunks, making images semantic-searchable.

--------------------------------------------------------------------------------
4.3 Dense Text Embedding Module (`app/core/embedder.py`)
--------------------------------------------------------------------------------
• Loads `BAAI/bge-base-en-v1.5` on PyTorch / CPU / MPS / CUDA.
• Documents are embedded as-is in batches (default batch size: 32).
• Queries automatically receive the required BGE prefix: 
  "Represent this sentence for searching relevant passages: "
• All output embeddings are L2-normalized so dot-product equals cosine similarity.

--------------------------------------------------------------------------------
4.4 Vector Storage & Indexing Engine (`app/core/vector_store.py`)
--------------------------------------------------------------------------------
ChromaDB persistent client manages storage under `./data/chroma_db`:
• Dual Collection Strategy:
  1. Manual-Specific Collection (`manual_{manual_id}`): Enables scoped search.
  2. Unified Collection (`all_manuals`): Enables cross-manual global search.
• Metadata Payload:
  Includes `source_file`, `manual_id`, `page_number`, `chunk_index`, `content_type`, 
  `section_header`, `image_path`, and `page_image_path`.

--------------------------------------------------------------------------------
4.5 Cross-Encoder Reranking Engine (`app/core/reranker.py`)
--------------------------------------------------------------------------------
• Uses `BAAI/bge-reranker-v2-m3` CrossEncoder.
• Takes initial candidate chunks (default Top-15 from bi-encoder vector search).
• Scores joint `(query, document_text)` representations to evaluate deep semantic relevance.
• Sorts by rerank score descending and returns the Top-N (default: 5) chunks to LLM.

--------------------------------------------------------------------------------
4.6 Diagnostic Generation Engine (`app/core/generator.py`)
--------------------------------------------------------------------------------
• Context & Image Assembly: Assembles formatted text excerpts + source metadata. 
  Loads and resizes up to 4 unique page/diagram images referenced in the top chunks.
• Dual Mode Operation:
  - Standard REST Endpoint (`POST /query`):
    Uses `SYSTEM_PROMPT` commanding valid JSON output:
    { "answer": "...", "possible_issues": [...], "recommended_solutions": [...], "safety_warnings": [...] }
  - Streaming Endpoint (`POST /query/stream`):
    Uses `STREAM_SYSTEM_PROMPT` commanding Markdown structure with headers:
    `## Diagnosis`, `## Possible Issues`, `## Recommended Solutions`, `## ⚠️ Safety Warnings`.
    Yields tokens over Server-Sent Events (SSE).

================================================================================
5. API ROUTE SPECIFICATIONS & ENDPOINTS
================================================================================

1. System Health Check
   • Method/Path: GET /health
   • Description: Returns status of Ollama connection, VLM availability, model loading, and database record counts.

2. Ingest PDF Manual
   • Method/Path: POST /ingest
   • Content-Type: multipart/form-data (file=@manual.pdf)
   • Response: IngestResponse JSON with chunk & caption counts and processing runtime.

3. List Ingested Manuals
   • Method/Path: GET /ingest/manuals
   • Response: List of indexed manuals with manual_id, filename, and chunk counts.

4. Delete Ingested Manual
   • Method/Path: DELETE /ingest/manuals/{manual_id}
   • Response: Confirmation message after removing vector store entries & images.

5. Query RAG Pipeline (REST)
   • Method/Path: POST /query
   • Body: { "query": "Motor overheating with noise", "manual_filter": null, "top_k": 5 }
   • Response: QueryResponse JSON containing full structured answer, issues, solutions, warnings, and source attribution array.

6. Query RAG Pipeline (Streaming SSE)
   • Method/Path: POST /query/stream
   • Content-Type: text/event-stream
   • Events:
     - `event: sources`: JSON array of retrieved sources.
     - `event: token`: Incremental response token chunk.
     - `event: done`: Execution timing stats.

================================================================================
6. FRONTEND USER INTERFACE & INTEGRATION
================================================================================
The project includes a lightweight web interface located under `/frontend`:
• Built with Vanilla JavaScript ES6, HTML5, and CSS3.
• Real-time SSE parsing: Consumes `/query/stream` using fetch ReadableStream and renders formatted Markdown dynamically.
• Source Drawer & Image Modal: Clickable source references display rendered page images and extracted diagrams directly in the browser.
• Manual Management Panel: Allows users to drag-and-drop PDFs for upload and inspect indexed manual libraries.

================================================================================
7. CONFIGURATION & ENVIRONMENT VARIABLES
================================================================================
Settings are loaded via Pydantic from `.env`:

Key Config Variable       Default Value                   Description
--------------------------------------------------------------------------------
OLLAMA_BASE_URL           http://127.0.0.1:11434          Ollama HTTP service endpoint
OLLAMA_VISION_MODEL       qwen2.5vl:3b                    Ollama vision model tag
EMBEDDING_MODEL_NAME      BAAI/bge-base-en-v1.5           HuggingFace embedding model
RERANKER_MODEL_NAME       BAAI/bge-reranker-v2-m3         HuggingFace reranker model
DATA_DIR                  ./data                          Root directory for app data
CHROMA_PERSIST_DIR        ./data/chroma_db                ChromaDB persistent directory
IMAGE_STORE_DIR           ./data/images                   Rendered image storage
CHUNK_SIZE                512                             Text chunk character size
CHUNK_OVERLAP             64                              Text chunk character overlap
TOP_K_RETRIEVAL           15                              Initial bi-encoder search depth
TOP_K_RERANK              5                               Final top chunks sent to LLM
HOST                      0.0.0.0                         Uvicorn server host
PORT                      8000                            Uvicorn server port

================================================================================
8. DEPLOYMENT & OPERATION GUIDE
================================================================================

A. Running Locally (Direct Python Environment):
1. Install Python dependencies:
   `pip install -r requirements.txt`
2. Start Ollama daemon and pull the vision model:
   `ollama serve`
   `ollama pull qwen2.5vl:3b`
3. Launch FastAPI backend:
   `uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. Access API Docs: `http://localhost:8000/docs`

B. Running via Docker Compose:
`docker compose up -d`
This spins up both the `ollama` container and the `rag-api` container automatically.

================================================================================
9. KNOWN TROUBLESHOOTING & EDGE CASES
================================================================================
1. IPv4 vs IPv6 Host Resolution on macOS:
   On macOS, `localhost` resolves to IPv6 `[::1]`. If native Ollama runs on IPv4 
   `127.0.0.1`, set `OLLAMA_BASE_URL=http://127.0.0.1:11434` in `.env` to avoid 
   404 Connection refused / model not found errors.

2. Heavy VLM Ingestion Times:
   Captioning pages with heavy graphics using a 7B or 11B vision model can take 
   several seconds per page on CPU. VRAM GPU acceleration (NVIDIA CUDA or Apple Silicon MPS) 
   is recommended for fast ingestion of multi-hundred page manuals.
================================================================================
