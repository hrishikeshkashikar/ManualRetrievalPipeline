#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
#  export_image.sh — Export the Manual RAG Docker image for air-gapped transfer
#
#  Saves the image as a compressed .tar.gz file that can be:
#    • Copied to a USB drive
#    • Transferred over a network
#    • Deployed to any machine without internet access
#
#  Usage:
#    ./scripts/export_image.sh [OPTIONS]
#
#  Options:
#    --image  <tag>    Image to export (default: manual-rag:latest)
#    --out    <file>   Output file path (default: ./manual-rag-full.tar.gz)
#    --help            Show this help
#
#  Examples:
#    ./scripts/export_image.sh
#    ./scripts/export_image.sh --image manual-rag:3b --out ./exports/rag-3b.tar.gz
# ══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────
IMAGE_TAG="manual-rag:latest"
OUTPUT_FILE="./manual-rag-full.tar.gz"

# ── Parse args ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --image) IMAGE_TAG="$2";   shift 2 ;;
    --out)   OUTPUT_FILE="$2"; shift 2 ;;
    --help)
      sed -n '2,25p' "$0"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Preflight ─────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Manual RAG — Export Docker Image                       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Source image : ${IMAGE_TAG}"
echo "  Output file  : ${OUTPUT_FILE}"
echo ""

if ! docker image inspect "${IMAGE_TAG}" &>/dev/null; then
  echo "✗ Image '${IMAGE_TAG}' not found."
  echo "  Build it first: ./scripts/build.sh"
  exit 1
fi

IMAGE_SIZE=$(docker image inspect "${IMAGE_TAG}" --format='{{.Size}}' | awk '{printf "%.1f GB", $1/1073741824}')
echo "  Uncompressed size: ${IMAGE_SIZE}"
echo "  Compressed size will be smaller (est. 30–50% reduction)"
echo ""

# ── Export ────────────────────────────────────────────────────────────────
mkdir -p "$(dirname "${OUTPUT_FILE}")"

echo "▸ Exporting and compressing image (this may take a few minutes)..."
EXPORT_START=$(date +%s)

docker save "${IMAGE_TAG}" | gzip -9 > "${OUTPUT_FILE}"

EXPORT_END=$(date +%s)
EXPORT_TIME=$((EXPORT_END - EXPORT_START))
COMPRESSED_SIZE=$(du -sh "${OUTPUT_FILE}" | cut -f1)

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ✓ Export complete!                                     ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  File         : ${OUTPUT_FILE}"
echo "  Size         : ${COMPRESSED_SIZE}"
echo "  Export time  : $((EXPORT_TIME / 60))m $((EXPORT_TIME % 60))s"
echo ""
echo "▸ Transfer to target machine, then run:"
echo "    ./scripts/load_and_run.sh --image ${OUTPUT_FILE}"
echo ""
echo "▸ Files to copy to the target machine:"
echo "    1. ${OUTPUT_FILE}"
echo "    2. docker-compose.yml"
echo "    3. scripts/load_and_run.sh"
echo "    4. Your data/ folder (knowledge base)"
echo ""
