#!/bin/bash
# ════════════════════════════════════════════════════════════════════
# Setup Models — Run ONCE on a machine WITH internet access
#
# Downloads all required models for offline operation:
#   1. Ollama vision model
#   2. Sentence-transformers embedding model
#   3. Cross-encoder reranker model
#
# After running this script, transfer the following directories
# to your edge device:
#   - ~/.ollama/models/
#   - ~/.cache/huggingface/
# ════════════════════════════════════════════════════════════════════

set -euo pipefail

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Machine Manual RAG — Model Setup                       ║"
echo "╚══════════════════════════════════════════════════════════╝"

# Configuration (override via environment variables)
VISION_MODEL="${OLLAMA_VISION_MODEL:-llama3.2-vision:11b}"
EMBEDDING_MODEL="${EMBEDDING_MODEL_NAME:-BAAI/bge-base-en-v1.5}"
RERANKER_MODEL="${RERANKER_MODEL_NAME:-BAAI/bge-reranker-v2-m3}"

# ── Step 1: Ollama Vision Model ──────────────────────────────────
echo ""
echo "▸ Step 1/3: Pulling Ollama vision model: ${VISION_MODEL}"
echo "  This may take a while depending on model size..."

if command -v ollama &> /dev/null; then
    ollama pull "${VISION_MODEL}"
    echo "  ✓ Ollama model ready"
else
    echo "  ✗ Ollama not found. Install from: https://ollama.com"
    echo "  After installing, run: ollama pull ${VISION_MODEL}"
fi

# ── Step 2: Embedding Model ─────────────────────────────────────
echo ""
echo "▸ Step 2/3: Downloading embedding model: ${EMBEDDING_MODEL}"

python3 -c "
from sentence_transformers import SentenceTransformer
print('  Downloading...')
model = SentenceTransformer('${EMBEDDING_MODEL}')
dim = model.get_sentence_embedding_dimension()
print(f'  ✓ Embedding model ready (dimension: {dim})')
"

# ── Step 3: Reranker Model ──────────────────────────────────────
echo ""
echo "▸ Step 3/3: Downloading reranker model: ${RERANKER_MODEL}"

python3 -c "
from sentence_transformers import CrossEncoder
print('  Downloading...')
model = CrossEncoder('${RERANKER_MODEL}')
print('  ✓ Reranker model ready')
"

# ── Summary ─────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ✓ All models downloaded successfully!                  ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "To deploy on an edge device without internet:"
echo "  1. Copy ~/.ollama/models/     → edge:~/.ollama/models/"
echo "  2. Copy ~/.cache/huggingface/ → edge:~/.cache/huggingface/"
echo "  3. Set HF_HUB_OFFLINE=1 in the environment"
echo "  4. Run: uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
