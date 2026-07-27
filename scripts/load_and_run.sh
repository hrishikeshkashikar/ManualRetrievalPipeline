#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
#  load_and_run.sh — Load a Manual RAG image and start the application
#
#  Run this on the TARGET machine (edge server / deployment host).
#  No internet access required — all models are in the image.
#
#  Prerequisites:
#    • Docker installed (any version with compose support)
#    • The exported .tar.gz image file
#    • A docker-compose.yml (copy from the source project)
#    • Your data/ knowledge-base folder
#
#  Usage:
#    ./load_and_run.sh [OPTIONS]
#
#  Options:
#    --image  <file>    Path to the .tar.gz image file
#                       (default: ./manual-rag-full.tar.gz)
#    --data   <path>    Path to your knowledge-base data folder
#                       (default: ./data)
#    --port   <port>    Host port to expose the UI on (default: 8000)
#    --help             Show this help
#
#  Examples:
#    ./load_and_run.sh
#    ./load_and_run.sh --image /media/usb/manual-rag-full.tar.gz --data /media/usb/data
#    ./load_and_run.sh --image ./exports/rag-3b.tar.gz --port 9000
# ══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────
IMAGE_FILE="./manual-rag-full.tar.gz"
DATA_PATH="./data"
HOST_PORT="8000"

# ── Parse args ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --image) IMAGE_FILE="$2"; shift 2 ;;
    --data)  DATA_PATH="$2";  shift 2 ;;
    --port)  HOST_PORT="$2";  shift 2 ;;
    --help)
      sed -n '2,30p' "$0"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Banner ────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Manual RAG — Load & Run (Air-Gapped Deployment)        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Image file   : ${IMAGE_FILE}"
echo "  Data path    : ${DATA_PATH}"
echo "  UI port      : ${HOST_PORT}"
echo ""

# ── Preflight ─────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "✗ Docker not found. Install Docker Engine:"
  echo "  https://docs.docker.com/engine/install/"
  exit 1
fi

if [ ! -f "${IMAGE_FILE}" ]; then
  echo "✗ Image file not found: ${IMAGE_FILE}"
  echo "  Copy the .tar.gz from the build machine and try again."
  exit 1
fi

# ── Load image ────────────────────────────────────────────────────────────
echo "▸ Loading image from ${IMAGE_FILE}..."
echo "  (This may take 1–5 minutes depending on disk speed)"
LOAD_START=$(date +%s)

docker load < "${IMAGE_FILE}"

LOAD_END=$(date +%s)
echo "  ✓ Image loaded in $(( (LOAD_END - LOAD_START) / 60 ))m $(( (LOAD_END - LOAD_START) % 60 ))s"
echo ""

# ── Ensure data structure ─────────────────────────────────────────────────
echo "▸ Ensuring knowledge-base directory structure..."
mkdir -p \
    "${DATA_PATH}/chroma_db" \
    "${DATA_PATH}/images" \
    "${DATA_PATH}/manuals"
echo "  ✓ Data directory: ${DATA_PATH}"
echo ""

# ── Write a minimal docker-compose if none exists ─────────────────────────
if [ ! -f "docker-compose.yml" ]; then
  echo "▸ No docker-compose.yml found — generating a minimal one..."
  cat > docker-compose.yml <<EOF
services:
  manual-rag:
    image: manual-rag:latest
    container_name: manual-rag-app
    ports:
      - "${HOST_PORT}:8000"
      - "11434:11434"
    volumes:
      - ${DATA_PATH}:/app/data
      # Add extra knowledge bases below:
      # - /path/to/other-kb:/kb/other
    environment:
      - OLLAMA_BASE_URL=http://127.0.0.1:11434
      - HF_HOME=/opt/hf_models
      - HF_HUB_OFFLINE=1
      - TRANSFORMERS_OFFLINE=1
      - DATA_DIR=/app/data
      - CHROMA_PERSIST_DIR=/app/data/chroma_db
      - IMAGE_STORE_DIR=/app/data/images
      - MANUAL_STORE_DIR=/app/data/manuals
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
EOF
  echo "  ✓ docker-compose.yml created"
  echo ""
fi

# ── Start ─────────────────────────────────────────────────────────────────
echo "▸ Starting Manual RAG..."
docker compose up -d

echo ""
echo "▸ Waiting for health check to pass (up to 90 seconds)..."
HEALTH_WAIT=0
while [ $HEALTH_WAIT -lt 90 ]; do
  STATUS=$(docker inspect --format='{{.State.Health.Status}}' manual-rag-app 2>/dev/null || echo "starting")
  if [ "$STATUS" = "healthy" ]; then
    break
  fi
  sleep 5
  HEALTH_WAIT=$((HEALTH_WAIT + 5))
  echo "  ... ${HEALTH_WAIT}s — status: ${STATUS}"
done

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ✓ Manual RAG is running!                               ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Web UI   : http://localhost:${HOST_PORT}"
echo "  API Docs : http://localhost:${HOST_PORT}/docs"
echo "  Health   : http://localhost:${HOST_PORT}/health"
echo ""
echo "▸ To switch knowledge bases:"
echo "  1. Add more volume mounts to docker-compose.yml"
echo "  2. Run: docker compose up -d"
echo "  3. In the UI, click 'Change Data Path' → enter /kb/<name>"
echo ""
echo "▸ To view logs:"
echo "    docker compose logs -f"
echo ""
echo "▸ To stop:"
echo "    docker compose down"
echo ""
