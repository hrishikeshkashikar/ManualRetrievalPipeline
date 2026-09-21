# ManualRetrievalPipeline — Setup Instructions

> **Audience:** Anyone receiving this repo for the first time.
> **Goal:** Get the application running on your own machine from scratch.
> **Time required:** ~30–60 minutes (mostly model downloads on first run).

---

## Table of Contents

1. [What This App Does](#1-what-this-app-does)
2. [Prerequisites](#2-prerequisites)
3. [Clone the Repository from GitHub](#3-clone-the-repository-from-github)
4. [Choose Your Setup Path](#4-choose-your-setup-path)
   - [Path A — Docker (Recommended)](#path-a--docker-recommended-easiest)
   - [Path B — Run Locally (No Docker)](#path-b--run-locally-without-docker)
5. [First-Time Usage Walkthrough](#5-first-time-usage-walkthrough)
6. [Verifying Everything Works](#6-verifying-everything-works)
7. [Default Login Credentials](#7-default-login-credentials)
8. [Configuration Reference](#8-configuration-reference)
9. [Stopping & Restarting](#9-stopping--restarting)
10. [Troubleshooting](#10-troubleshooting)
11. [Project Structure Overview](#11-project-structure-overview)

---

## 1. What This App Does

This is a **fully offline, local RAG (Retrieval-Augmented Generation) system** for machine manual diagnosis. You can:

- **Upload PDF manuals** (including ones with diagrams, schematics, wiring charts)
- **Ask natural-language questions** about machine problems
- **Get structured diagnostic responses** with possible issues, step-by-step solutions, safety warnings, and exact page/section references

Everything runs 100% on your machine — no data ever leaves your device.

---

## 2. Prerequisites

### Required Software

| Software | Version | Download Link | Why You Need It |
|----------|---------|---------------|-----------------|
| **Git** | Any recent | [git-scm.com](https://git-scm.com/downloads) | To clone the repo |
| **Ollama** | v0.4.0+ | [ollama.com](https://ollama.com/download) | Runs the AI vision model locally |

**Plus ONE of the following** (depending on which setup path you choose):

| Setup Path | Additional Software | Download Link |
|------------|-------------------|---------------|
| **Path A (Docker)** | Docker Desktop | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **Path B (Local)** | Python 3.11+ | [python.org](https://www.python.org/downloads/) |

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **RAM** | 8 GB | 16 GB+ |
| **Disk Space** | 10 GB free | 20 GB free |
| **GPU (optional)** | — | NVIDIA GPU (CUDA) or Apple Silicon (M1/M2/M3/M4) |

> **Note:** The app works on CPU-only machines, but will be significantly faster with GPU acceleration. Apple Silicon Macs automatically use the GPU via Metal/MPS.

---

## 3. Clone the Repository from GitHub

### Step 3.1 — Open a Terminal

| OS | How to Open Terminal |
|----|---------------------|
| **macOS** | Press `Cmd + Space`, type **Terminal**, press Enter |
| **Windows** | Press `Win + R`, type **cmd** or **powershell**, press Enter |
| **Linux** | Press `Ctrl + Alt + T` |

### Step 3.2 — Clone the Repo

```bash
git clone https://github.com/hrishikeshkashikar/ManualRetrievalPipeline.git
```

> ⚠️ **If the repo is private**, you'll be prompted for your GitHub username and a Personal Access Token (not your password). Ask the repo owner to add you as a collaborator first.

### Step 3.3 — Navigate into the Project

```bash
cd ManualRetrievalPipeline
```

---

## 4. Choose Your Setup Path

### Which path should I pick?

| | **Path A — Docker** | **Path B — Local Python** |
|---|---|---|
| **Best for** | Quick setup, no Python experience needed | Full control, development, debugging |
| **Pros** | One command to run; fully isolated; no dependency conflicts | Faster startup; easier to modify code |
| **Cons** | Requires Docker Desktop (~2 GB install) | Requires Python setup; more manual steps |

---

### Path A — Docker (Recommended, Easiest)

This builds a self-contained Docker image with ALL models baked in. After the initial build, it works completely offline.

#### A.1 — Install & Start Docker Desktop

1. Download from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
2. Install and launch Docker Desktop
3. **Wait until Docker Desktop shows "Engine Running"** (green icon in system tray/menu bar)

Verify Docker is working:
```bash
docker --version
docker compose version
```
You should see version numbers printed (not errors).

#### A.2 — Install & Start Ollama

1. Download from [ollama.com/download](https://ollama.com/download)
2. Install and launch Ollama

Verify Ollama is working:
```bash
ollama --version
```

#### A.3 — Build the Docker Image (One-Time, Needs Internet)

From inside the project directory, run:

```bash
chmod +x scripts/*.sh
./scripts/build.sh --model qwen2.5vl:3b
```

> ☕ **This will take 10–30 minutes** the first time. It downloads the vision model (~2 GB), embedding model, and reranker model, and bakes them all into the Docker image. You only need to do this once.

**On Windows** (if not using Git Bash or WSL):
```powershell
docker build --build-arg VISION_MODEL=qwen2.5vl:3b -t manual-rag:latest .
```

#### A.4 — Start the Application

```bash
./scripts/run.sh
```

**Or manually with Docker Compose:**
```bash
docker compose up -d
```

#### A.5 — Open the App

Open your web browser and go to:

> **http://localhost:8000**

🎉 **You're done!** Skip to [Section 5 — First-Time Usage Walkthrough](#5-first-time-usage-walkthrough).

---

### Path B — Run Locally (Without Docker)

#### B.1 — Install Python 3.11+

Download from [python.org/downloads](https://www.python.org/downloads/) and install.

Verify:
```bash
python3 --version
```
You should see `Python 3.11.x` or higher.

#### B.2 — Install Ollama

1. Download from [ollama.com/download](https://ollama.com/download)
2. Install and launch Ollama

Verify:
```bash
ollama --version
```

#### B.3 — Create a Virtual Environment

```bash
python3 -m venv venv
```

**Activate it:**

| OS | Command |
|----|---------|
| **macOS / Linux** | `source venv/bin/activate` |
| **Windows (cmd)** | `venv\Scripts\activate` |
| **Windows (PowerShell)** | `venv\Scripts\Activate.ps1` |

You should see `(venv)` appear at the beginning of your terminal prompt.

#### B.4 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

> This installs FastAPI, PyTorch, sentence-transformers, ChromaDB, and other dependencies. May take a few minutes.

#### B.5 — Download AI Models (One-Time, Needs Internet)

```bash
chmod +x scripts/setup_models.sh
./scripts/setup_models.sh
```

This downloads three models:
1. **Ollama vision model** (`qwen2.5vl:3b`) — ~2 GB
2. **BGE embedding model** — ~400 MB
3. **BGE reranker model** — ~500 MB

> **On Windows**, if you can't run the bash script, do it manually:
> ```bash
> ollama pull qwen2.5vl:3b
> ```
> The embedding and reranker models will auto-download on first app launch.

#### B.6 — Configure Environment Variables

```bash
cp .env.example .env
```

The defaults work out of the box. Edit `.env` only if you need to change model names, ports, or paths. See [Section 8](#8-configuration-reference) for details.

#### B.7 — Start Ollama (if not already running)

Ollama usually runs as a background service after installation. Verify with:
```bash
ollama list
```
If it says "connection refused", start Ollama manually:
```bash
ollama serve
```
(Leave this terminal open and open a new terminal for the next step.)

#### B.8 — Start the Application

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

You should see output like:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Loading embedding model...
INFO:     Loading reranker model...
INFO:     Application startup complete.
```

#### B.9 — Open the App

Open your web browser and go to:

> **http://localhost:8000**

🎉 **You're done!** Continue to the next section.

---

## 5. First-Time Usage Walkthrough

### Step 1 — Log In

When you first open `http://localhost:8000`, you'll see a login page.

- **Username:** `admin`
- **Password:** `admin`

(You can change these later — see [Section 7](#7-default-login-credentials).)

### Step 2 — Upload a PDF Manual

1. Click the **"Ingest"** tab or the manual management panel in the sidebar
2. **Drag and drop** a PDF file, or click to browse
3. Wait for processing to complete — you'll see a progress indicator

> **What happens behind the scenes:**
> - Every page is rendered as an image
> - Diagrams and schematics are analyzed by the vision AI model
> - Text is chunked and embedded into a searchable vector database
>
> Processing time depends on PDF size and your hardware. A 50-page manual typically takes 2–10 minutes.

### Step 3 — Ask a Question

1. Switch to the **"Query"** tab
2. Type a question like:
   - *"The motor is overheating and making a grinding noise"*
   - *"What is the lubrication schedule for the main bearing?"*
   - *"Show me the wiring diagram for the control panel"*
3. Press Enter or click Send

### Step 4 — Review the Response

The system returns:
- **Diagnosis** — a detailed answer referencing the manual
- **Possible Issues** — ranked list of probable causes
- **Recommended Solutions** — step-by-step repair instructions
- **Safety Warnings** — highlighted safety precautions from the manual
- **Sources** — exact PDF filename, page number, and section, with clickable page image previews

---

## 6. Verifying Everything Works

### Quick Health Check (Browser)

Open: **http://localhost:8000/health**

You should see a JSON response with all fields showing `true`:
```json
{
  "status": "healthy",
  "ollama_connected": true,
  "ollama_model_available": true,
  "embedding_model_loaded": true,
  "reranker_loaded": true,
  "vector_store_ready": true
}
```

### Detailed Health Check (Terminal)

```bash
python scripts/health_check.py
```

Expected output:
```
Machine Manual RAG — Health Check
==================================================
  ✓ Overall Status: healthy
  ✓ Ollama Connected: True
  ✓ Vision Model Available: True
  ✓ Embedding Model Loaded: True
  ✓ Reranker Loaded: True
  ✓ Vector Store Ready: True

✓ All systems operational!
```

### Interactive API Docs

Open: **http://localhost:8000/docs**

This gives you a Swagger UI where you can test all API endpoints directly.

---

## 7. Default Login Credentials

| Field | Default Value |
|-------|---------------|
| Username | `admin` |
| Password | `admin` |

**To change the defaults**, edit the `.env` file:
```env
AUTH_USERNAME=your_username
AUTH_PASSWORD=your_secure_password
AUTH_SECRET=some-random-secret-string
```

If using Docker, restart the container after changing:
```bash
docker compose down && docker compose up -d
```

---

## 8. Configuration Reference

The app is configured via a `.env` file. Create it by copying the example:
```bash
cp .env.example .env
```

### Key Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama API endpoint |
| `OLLAMA_VISION_MODEL` | `qwen2.5vl:3b` | Vision model to use (must be pulled in Ollama) |
| `OLLAMA_NUM_CTX` | `32768` | Context window size (reduce to `8192` on 8 GB RAM machines) |
| `DATA_DIR` | `./data` | Where manuals, embeddings, and images are stored |
| `AUTH_ENABLED` | `true` | Enable/disable login |
| `AUTH_USERNAME` | `admin` | Default login username |
| `AUTH_PASSWORD` | `admin` | Default login password |
| `QUERY_ONLY` | `false` | Set `true` to disable PDF upload (query-only mode) |
| `ENABLE_RERANKER` | `true` | Set `false` on low-RAM machines to save ~1 GB |
| `TOP_K_RETRIEVAL` | `15` | Number of chunks retrieved in initial search |
| `TOP_K_RERANK` | `5` | Number of chunks after reranking sent to the LLM |

### Vision Model Options

| Model | Size | RAM Needed | Quality | Speed |
|-------|------|-----------|---------|-------|
| `qwen2.5vl:3b` | ~2 GB | 8 GB+ | Good | Fast |
| `qwen2.5vl:7b` | ~5 GB | 16 GB+ | Better | Moderate |
| `llama3.2-vision:11b` | ~7 GB | 16 GB+ | Best | Slower |

To switch models:
```bash
ollama pull qwen2.5vl:7b
```
Then update `OLLAMA_VISION_MODEL=qwen2.5vl:7b` in your `.env` file and restart.

---

## 9. Stopping & Restarting

### Docker

```bash
# Stop
docker compose down

# Start again
docker compose up -d

# View logs
docker compose logs -f

# Restart
docker compose restart
```

### Local (Python)

```bash
# Stop: press Ctrl+C in the terminal running uvicorn

# Start again:
source venv/bin/activate      # macOS/Linux
# venv\Scripts\activate       # Windows
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 10. Troubleshooting

### "Cannot connect to Ollama" / Ollama not found

**Cause:** Ollama is not running.

**Fix:**
- **macOS:** Launch the Ollama app from Applications, or run `ollama serve`
- **Windows:** Launch Ollama from the Start menu
- **Linux:** Run `ollama serve` in a separate terminal

### "Model not found" error

**Cause:** The vision model hasn't been downloaded.

**Fix:**
```bash
ollama pull qwen2.5vl:3b
```

### macOS — "Connection refused" when Ollama is running

**Cause:** macOS `localhost` resolves to IPv6 (`::1`), but Ollama binds to IPv4 (`127.0.0.1`).

**Fix:** Set this in your `.env`:
```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

### Docker — "Cannot connect to the Docker daemon"

**Cause:** Docker Desktop is not running.

**Fix:** Open Docker Desktop and wait for the engine to start (green icon).

### Slow ingestion (pages taking minutes each)

**Cause:** Large vision model on CPU.

**Fix:** Use the smaller model:
```env
OLLAMA_VISION_MODEL=qwen2.5vl:3b
```
Or if you have a GPU, Ollama will use it automatically.

### Port 8000 already in use

**Fix:** Change the port:
```bash
# Docker
API_PORT=9000 docker compose up -d

# Local
uvicorn app.main:app --host 0.0.0.0 --port 9000
```
Then open `http://localhost:9000`.

---

## 11. Project Structure Overview

```
ManualRetrievalPipeline/
├── app/                          # Python backend (FastAPI)
│   ├── main.py                   #   Application entry point
│   ├── config.py                 #   Configuration loader
│   ├── api/                      #   API route handlers (ingest, query, health)
│   ├── auth/                     #   Authentication logic
│   ├── core/                     #   Core business logic
│   │   ├── pdf_processor.py      #     PDF → text + images
│   │   ├── vision_captioner.py   #     Image → text captions (via Ollama)
│   │   ├── embedder.py           #     Text → vector embeddings
│   │   ├── vector_store.py       #     ChromaDB operations
│   │   ├── reranker.py           #     Cross-encoder reranking
│   │   ├── generator.py          #     LLM answer generation
│   │   └── rag_pipeline.py       #     Orchestrator
│   └── models/                   #   Pydantic request/response schemas
├── frontend/                     # Web UI (HTML + CSS + JS)
│   ├── index.html                #   Main page
│   ├── css/                      #   Stylesheets
│   └── js/                       #   JavaScript modules
├── scripts/                      # Setup & utility scripts
│   ├── setup_models.sh           #   Download all AI models
│   ├── build.sh                  #   Build Docker image
│   ├── run.sh                    #   Start via Docker
│   ├── health_check.py           #   Verify system health
│   └── ...                       #   Export, edge deployment scripts
├── data/                         # Runtime data (auto-created)
│   ├── manuals/                  #   Uploaded PDF files
│   ├── images/                   #   Rendered page images
│   └── chroma_db/                #   Vector database
├── tests/                        # Test suite
├── Dockerfile                    # Full self-contained image
├── Dockerfile.edge               # Lightweight query-only image
├── docker-compose.yml            # Docker Compose config
├── docker-compose.edge.yml       # Edge deployment config
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variable template
├── README.md                     # Project README
└── TECHNICAL_DOCUMENTATION.md    # Detailed architecture docs
```

---

## Quick Reference — Copy-Paste Cheat Sheet

### macOS / Linux — Docker (fastest path)

```bash
# 1. Clone
git clone https://github.com/hrishikeshkashikar/ManualRetrievalPipeline.git
cd ManualRetrievalPipeline

# 2. Make scripts executable
chmod +x scripts/*.sh

# 3. Build (one-time, needs internet, ~15 min)
./scripts/build.sh --model qwen2.5vl:3b

# 4. Run
./scripts/run.sh

# 5. Open browser → http://localhost:8000
# Login: admin / admin
```

### macOS / Linux — Local Python

```bash
# 1. Clone
git clone https://github.com/hrishikeshkashikar/ManualRetrievalPipeline.git
cd ManualRetrievalPipeline

# 2. Virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download models (one-time, needs internet)
chmod +x scripts/setup_models.sh
./scripts/setup_models.sh

# 5. Configure
cp .env.example .env

# 6. Start Ollama (if not already running)
ollama serve &

# 7. Run the app
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 8. Open browser → http://localhost:8000
# Login: admin / admin
```

### Windows — Local Python (PowerShell)

```powershell
# 1. Clone
git clone https://github.com/hrishikeshkashikar/ManualRetrievalPipeline.git
cd ManualRetrievalPipeline

# 2. Virtual environment
python -m venv venv
venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download Ollama vision model
ollama pull qwen2.5vl:3b

# 5. Configure
copy .env.example .env

# 6. Run the app
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 7. Open browser → http://localhost:8000
# Login: admin / admin
```

---

> **Questions or issues?** Contact the repo owner or open a GitHub Issue on the repository.
