#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
#  entrypoint.sh — Docker container startup script
#
#  Startup sequence:
#    1. Create required data sub-directories if not present
#    2. Start supervisord (which launches ollama serve)
#    3. Poll Ollama's /api/tags until it responds (health-check loop)
#    4. Verify the vision model is available inside the container
#    5. Signal supervisord to start the rag-api process
#
#  This script is the Docker ENTRYPOINT. supervisord manages process
#  lifecycle after handoff.
# ══════════════════════════════════════════════════════════════════════════

set -euo pipefail

OLLAMA_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
VISION_MODEL="${OLLAMA_VISION_MODEL:-qwen2.5vl:3b}"
MAX_WAIT=120   # seconds to wait for Ollama to become healthy
DATA_DIR="${DATA_DIR:-/app/data}"

# ── Banner ────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Machine Manual RAG Pipeline — Starting Up              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Vision Model  : ${VISION_MODEL}"
echo "  Ollama URL    : ${OLLAMA_URL}"
echo "  Data Dir      : ${DATA_DIR}"
echo ""

# ── Ensure data directory structure ──────────────────────────────────────
echo "▸ Ensuring data directories exist..."
mkdir -p \
    "${DATA_DIR}/chroma_db" \
    "${DATA_DIR}/images" \
    "${DATA_DIR}/manuals"
echo "  ✓ Data directories ready"

# Create supervisor log directory
mkdir -p /var/log/supervisor
echo ""

# ── Start supervisord (Ollama + deferred API) ─────────────────────────────
echo "▸ Starting supervisord (Ollama will launch as process #1)..."
/usr/bin/supervisord -c /etc/supervisor/conf.d/manual-rag.conf &
SUPERVISOR_PID=$!
echo "  supervisord PID: ${SUPERVISOR_PID}"
echo ""

# ── Wait for Ollama to become ready ──────────────────────────────────────
echo "▸ Waiting for Ollama to become healthy (max ${MAX_WAIT}s)..."
ELAPSED=0
READY=false

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
        READY=true
        break
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    echo "  ... waiting ${ELAPSED}s / ${MAX_WAIT}s"
done

if [ "$READY" = false ]; then
    echo ""
    echo "✗ FATAL: Ollama did not become healthy within ${MAX_WAIT} seconds."
    echo "  Check /var/log/supervisor/ollama.err for details."
    exit 1
fi

echo "  ✓ Ollama is healthy after ${ELAPSED}s"
echo ""

# ── Verify the vision model is present (baked in during build) ────────────
echo "▸ Verifying vision model: ${VISION_MODEL}"
MODELS_JSON=$(curl -sf "${OLLAMA_URL}/api/tags" || echo '{"models":[]}')

if echo "${MODELS_JSON}" | grep -q "${VISION_MODEL%:*}"; then
    echo "  ✓ Model '${VISION_MODEL}' is available"
else
    echo "  ⚠ Model '${VISION_MODEL}' not found in Ollama — attempting pull..."
    /usr/local/bin/ollama pull "${VISION_MODEL}" || {
        echo "  ✗ Model pull failed. Ingestion will not work."
        echo "    If this is an air-gapped environment, rebuild the image"
        echo "    with the correct VISION_MODEL build arg."
    }
fi
echo ""

# ── Start the RAG API via supervisord ────────────────────────────────────
echo "▸ Starting RAG API (FastAPI + Uvicorn)..."
supervisorctl -s unix:///var/run/supervisor.sock start rag-api
echo "  ✓ rag-api process started"
echo ""

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ✓ All services running                                 ║"
echo "║    API:   http://0.0.0.0:8000                           ║"
echo "║    Docs:  http://0.0.0.0:8000/docs                      ║"
echo "║    Ollama http://0.0.0.0:11434                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  To switch knowledge bases from the UI:"
echo "  → Open the app → Click 'Change Data Path' in the sidebar"
echo "  → Enter a container-side path (e.g. /kb/project-alpha)"
echo ""

# Hand off to supervisord — it will keep both processes running
wait $SUPERVISOR_PID
