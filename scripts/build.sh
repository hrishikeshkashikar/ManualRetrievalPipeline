#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
#  build.sh — Build the self-contained Manual RAG Docker image
#
#  All models (Ollama vision + HuggingFace embedding + reranker) are
#  downloaded and baked into the image during this build.
#
#  IMPORTANT: Run this on a machine WITH internet access.
#             The resulting image is fully offline / air-gapped.
#
#  Usage:
#    ./scripts/build.sh [OPTIONS]
#
#  Options:
#    --model    <tag>   Ollama vision model to bake in (default: qwen2.5vl:3b)
#    --tag      <tag>   Docker image tag (default: manual-rag:latest)
#    --edge             Build/tag for 8GB query-only edge (default tag: manual-rag-query:latest)
#    --export           Export image to tar.gz after build
#    --no-cache         Force a clean rebuild (no Docker layer cache)
#    --help             Show this help
#
#  Examples:
#    ./scripts/build.sh
#    ./scripts/build.sh --model qwen2.5vl:3b --tag manual-rag:3b
#    ./scripts/build.sh --edge --export
#    ./scripts/build.sh --model qwen2.5vl:7b --export
#    ./scripts/build.sh --model llama3.2-vision:11b --tag manual-rag:11b --export
# ══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────
VISION_MODEL="qwen2.5vl:3b"
IMAGE_TAG="manual-rag:latest"
DO_EXPORT=false
NO_CACHE=""
EDGE_BUILD=false

# ── Parse args ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)   VISION_MODEL="$2"; shift 2 ;;
    --tag)     IMAGE_TAG="$2";    shift 2 ;;
    --edge)    EDGE_BUILD=true;   shift   ;;
    --export)  DO_EXPORT=true;    shift   ;;
    --no-cache) NO_CACHE="--no-cache"; shift ;;
    --help)
      sed -n '2,32p' "$0"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

if [ "$EDGE_BUILD" = true ] && [ "$IMAGE_TAG" = "manual-rag:latest" ]; then
  IMAGE_TAG="manual-rag-query:latest"
fi

# ── Preflight checks ───────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Manual RAG — Docker Image Build                        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Vision Model  : ${VISION_MODEL}"
echo "  Image Tag     : ${IMAGE_TAG}"
echo "  Edge profile  : ${EDGE_BUILD}"
echo "  Export        : ${DO_EXPORT}"
echo ""

if ! command -v docker &>/dev/null; then
  echo "✗ Docker not found. Install Docker Desktop or Docker Engine."
  exit 1
fi

if ! docker info &>/dev/null; then
  echo "✗ Docker daemon is not running. Start Docker and try again."
  exit 1
fi

# Warn about image size
echo "  ⚠ This build downloads and bakes in all models."
echo "    Estimated time : 10–30 min (depending on download speed)"
echo "    Estimated size : 8–10 GB (depending on vision model)"
if [ "$EDGE_BUILD" = true ]; then
  echo "    Edge note      : same image runtime; use docker-compose.edge.yml"
  echo "                     (QUERY_ONLY + low RAM env) on the target host."
fi
echo ""
echo "  Press Ctrl+C within 5 seconds to cancel..."
sleep 5
echo ""

# ── Build ──────────────────────────────────────────────────────────────────
echo "▸ Building image: ${IMAGE_TAG}"
echo "  Using vision model: ${VISION_MODEL}"
echo ""

BUILD_START=$(date +%s)

docker build \
  ${NO_CACHE} \
  --build-arg VISION_MODEL="${VISION_MODEL}" \
  --build-arg EMBEDDING_MODEL="BAAI/bge-base-en-v1.5" \
  --build-arg RERANKER_MODEL="BAAI/bge-reranker-v2-m3" \
  --tag "${IMAGE_TAG}" \
  --file Dockerfile \
  .

BUILD_END=$(date +%s)
BUILD_TIME=$((BUILD_END - BUILD_START))
BUILD_SIZE=$(docker image inspect "${IMAGE_TAG}" --format='{{.Size}}' | awk '{printf "%.1f GB", $1/1073741824}')

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ✓ Build complete!                                      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Image       : ${IMAGE_TAG}"
echo "  Size        : ${BUILD_SIZE}"
echo "  Build time  : $((BUILD_TIME / 60))m $((BUILD_TIME % 60))s"
echo ""

# ── Export ────────────────────────────────────────────────────────────────
if [ "$DO_EXPORT" = true ]; then
  echo "▸ Exporting image to tar.gz..."
  if [ "$EDGE_BUILD" = true ]; then
    ./scripts/export_image.sh --image "${IMAGE_TAG}" --out ./manual-rag-query.tar.gz
  else
    ./scripts/export_image.sh --image "${IMAGE_TAG}"
  fi
fi

if [ "$EDGE_BUILD" = true ]; then
  echo "▸ Edge deploy:"
  echo "    HOST_DATA_DIR=/path/to/data docker compose -f docker-compose.edge.yml up -d"
  echo "    # or: ./scripts/load_and_run_edge.sh --data /path/to/data"
else
  echo "▸ To start the application:"
  echo "    docker compose up -d"
fi
echo ""
echo "▸ To export for air-gapped deployment:"
echo "    ./scripts/export_image.sh --image ${IMAGE_TAG}"
echo ""
