# Machine Manual RAG Pipeline

A fully local, offline RAG (Retrieval-Augmented Generation) system for machine manual diagnosis. Upload PDF manuals — including those with diagrams, schematics, and tables — then ask questions about machine problems to get structured diagnostic responses.

## Features

- **Fully Offline** — Runs entirely on local hardware, no internet required after initial setup
- **Multimodal Understanding** — Interprets both text AND diagrams/images from manuals via a vision LLM
- **Structured Diagnosis** — Returns possible issues, step-by-step solutions, safety warnings, and source references
- **Fast Retrieval** — Semantic search with cross-encoder reranking for high-precision results
- **Edge-Ready** — Designed for deployment on edge devices with Docker support

## Architecture

```
PDF Upload → Text Extraction + Image Rendering + Diagram Extraction
           → VLM Captioning (diagrams → searchable text)
           → Embedding (BGE) → ChromaDB Storage

User Query → Embedding → Semantic Search → Cross-Encoder Reranking
           → Context Assembly (text + images)
           → VLM Generation → Structured Response
```

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running
- ~16 GB RAM (8 GB+ VRAM recommended for GPU acceleration)

### 1. Clone & Install

```bash
git clone <your-repo-url>
cd manal-rag-agent

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Download Models (requires internet — one time only)

```bash
chmod +x scripts/setup_models.sh
./scripts/setup_models.sh
```

This downloads:
- Ollama vision model (`llama3.2-vision:11b`)
- BGE embedding model
- BGE reranker model

### 3. Configure (optional)

```bash
cp .env.example .env
# Edit .env to customize model names, paths, etc.
```

### 4. Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Visit `http://localhost:8000/docs` for the interactive API documentation.

### 5. Verify

```bash
python scripts/health_check.py
```

## API Endpoints

| Method | Path | Description |
|:---|:---|:---|
| `GET` | `/health` | System health check |
| `POST` | `/ingest` | Upload and index a PDF manual |
| `GET` | `/ingest/manuals` | List all indexed manuals |
| `DELETE` | `/ingest/manuals/{id}` | Remove an indexed manual |
| `POST` | `/query` | Ask a question — get structured diagnosis |
| `POST` | `/query/stream` | Same, with streaming response |

### Example: Ingest a Manual

```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@/path/to/machine_manual.pdf"
```

### Example: Ask a Question

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "The motor is overheating and making a grinding noise"}'
```

### Example Response

```json
{
  "query": "The motor is overheating and making a grinding noise",
  "answer": "Based on the manual, motor overheating with grinding noise...",
  "possible_issues": [
    "Bearing failure (Section 3.2, Page 42)",
    "Cooling fan obstruction (Section 3.4, Page 45)"
  ],
  "recommended_solutions": [
    "1. Immediately shut down the motor and disconnect power",
    "2. Inspect bearings for wear — replace if play detected",
    "3. Clear any debris from the cooling fan assembly"
  ],
  "safety_warnings": [
    "Always disconnect power before inspection (Page 5)",
    "Allow motor to cool for 30 minutes before handling"
  ],
  "sources": [
    {
      "source_file": "motor_manual_v2.pdf",
      "page_number": 42,
      "section": "3.2 Bearing Maintenance",
      "relevance_score": 0.9234
    }
  ],
  "processing_time_seconds": 4.82
}
```

## Docker Deployment (recommended)

Self-contained image: Ollama + vision model + embedding/reranker models baked in.
The **data folder** (manuals, images, Chroma embeddings) is bind-mounted so you can
ingest on a powerful machine, copy the folder to a USB stick, and query offline elsewhere.

### 1. Build once (needs internet)

```bash
./scripts/build.sh --model qwen2.5vl:3b
# optional: ./scripts/build.sh --model qwen2.5vl:3b --export
```

### 2. Run locally

```bash
./scripts/run.sh                  # uses ./data
./scripts/run.sh /path/to/data    # or a USB path, e.g. /Volumes/USB/rag-data
```

Open http://localhost:8000/ — upload manuals (embeddings written into that folder).

### 3. Share with another machine / boss

```bash
./scripts/export_image.sh
# Copy manual-rag-full.tar.gz + docker-compose.yml + scripts/load_and_run.sh + your data/ folder
```

On the target machine (no internet needed after load):

```bash
./scripts/load_and_run.sh --image ./manual-rag-full.tar.gz --data /media/usb/rag-data
```

### 3b. Edge query-only (~8 GB RAM) + boss launcher

Ingest on a stronger machine, then ship only the `data/` folder + query image:

```bash
./scripts/build.sh --edge --export
./scripts/build_mac_dmg.sh          # optional: macOS ManualRAG.dmg
./scripts/export_for_edge.sh --with-data /path/to/data
# Bundle: exports/manual-rag-edge-bundle/ (ManualRAG.exe + ManualRAG.dmg)
```

On the edge PC: install Docker Desktop once, double-click `ManualRAG.exe` (Windows) or open `ManualRAG.dmg` → `ManualRAG.app` (Mac), enter/pick the `data/` path.
Or: `HOST_DATA_DIR=/path/to/data docker compose -f docker-compose.edge.yml up -d`

Validate locally: `./scripts/validate_edge_profile.sh`

### 4. Pendrive workflow

1. Powerful machine: `./scripts/run.sh --build ./data` → ingest PDFs in the UI  
2. Copy the entire `data/` folder to the USB stick  
3. Offline machine: `./scripts/run.sh /Volumes/YourUSB/data` (or Linux `/media/...`)  
4. Query — no re-embedding required  

The UI **Change Data Path** control can also switch folders under `/Users`, `/Volumes`,
`/home`, `/media`, or `/mnt` (mirrored into the container by `run.sh`).

## Project Structure

```
├── app/
│   ├── main.py              # FastAPI app + lifespan
│   ├── config.py             # Configuration
│   ├── api/                  # API route handlers
│   ├── core/                 # Business logic
│   │   ├── pdf_processor.py  # PDF → text + images
│   │   ├── vision_captioner.py  # Image → text captions
│   │   ├── embedder.py       # Text → vectors
│   │   ├── vector_store.py   # ChromaDB operations
│   │   ├── reranker.py       # Cross-encoder reranking
│   │   ├── generator.py      # VLM answer generation
│   │   └── rag_pipeline.py   # Orchestrator
│   └── models/               # Pydantic schemas
├── data/                     # Runtime data storage
├── scripts/                  # Setup & utility scripts
├── tests/                    # Test suite
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Future Roadmap

- [ ] **Whisper Integration** — Voice input via FastWhisper
- [ ] **Web UI** — Frontend for interactive use
- [ ] **Streaming UI** — Real-time token streaming
- [ ] **Multi-language** — Swap to BGE-M3 for multilingual support
- [ ] **Agentic RAG** — Tool-calling for complex multi-step diagnosis
