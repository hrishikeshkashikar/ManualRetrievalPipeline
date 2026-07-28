#!/usr/bin/env bash
# Package the current working Docker image for your boss / another machine.
#
# Exports what you have built (default: manual-rag-dev:latest) plus compose
# + a short README into ./exports/manual-rag-boss-bundle/
#
# Usage:
#   ./scripts/export_for_boss.sh
#   ./scripts/export_for_boss.sh --image manual-rag-dev:latest
#   ./scripts/export_for_boss.sh --with-data /Users/you/Downloads/data

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

IMAGE_TAG="manual-rag-dev:latest"
DATA_SRC=""
OUT_DIR="$ROOT/exports/manual-rag-boss-bundle"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image) IMAGE_TAG="$2"; shift 2 ;;
    --with-data) DATA_SRC="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    --help|-h) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "Unknown: $1" >&2; exit 1 ;;
  esac
done

if ! docker image inspect "$IMAGE_TAG" >/dev/null 2>&1; then
  echo "✗ Image '$IMAGE_TAG' not found. Build first:"
  echo "    docker compose -f docker-compose.dev.yml build"
  exit 1
fi

mkdir -p "$OUT_DIR"
TAR="$OUT_DIR/manual-rag-dev.tar.gz"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Export for boss                                         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo "  Image : $IMAGE_TAG"
echo "  Out   : $OUT_DIR"
echo ""

echo "▸ Saving image (several minutes, ~3–6 GB compressed)..."
docker save "$IMAGE_TAG" | gzip -1 > "$TAR"

cp docker-compose.boss.yml "$OUT_DIR/"
cp scripts/load_and_run.sh "$OUT_DIR/" 2>/dev/null || true

if [[ -n "$DATA_SRC" ]]; then
  echo "▸ Copying sample data from $DATA_SRC ..."
  mkdir -p "$OUT_DIR/sample-data"
  rsync -a --delete \
    --exclude '.DS_Store' \
    "$DATA_SRC/" "$OUT_DIR/sample-data/" 2>/dev/null \
    || cp -R "$DATA_SRC/." "$OUT_DIR/sample-data/"
fi

cat > "$OUT_DIR/README-BOSS.txt" <<'EOF'
Manual RAG — Quick start for your machine
=========================================

1) Install Docker Desktop and start it.
2) Install Ollama from https://ollama.com and pull the model:
     ollama pull qwen2.5vl:3b
3) Load the image (from this folder):
     gunzip -c manual-rag-dev.tar.gz | docker load
4) Create/choose a data folder (empty is fine), then start:

     # macOS example — use YOUR path
     HOST_DATA_DIR=/Users/YOURNAME/rag-data docker compose -f docker-compose.boss.yml up -d

     # USB / pendrive example
     HOST_DATA_DIR=/Volumes/USB/rag-data docker compose -f docker-compose.boss.yml up -d

5) Open http://localhost:8000/

Optional: if sample-data/ is included, you can point HOST_DATA_DIR at it
(or copy it to your preferred location first).

In the UI, "Change Data Path" also works for paths under:
  /Users/...   /Volumes/...   /home/...   /media/...   /mnt/...

Stop:
  docker compose -f docker-compose.boss.yml down

Notes:
- First start may download embedding models (needs internet once).
- For a fully offline / no-Ollama-install image, ask for the
  self-contained build (./scripts/build.sh + export).
EOF

echo ""
echo "✓ Bundle ready:"
du -sh "$OUT_DIR"/* 2>/dev/null | sed 's/^/  /'
echo ""
echo "Copy the whole folder to USB / AirDrop:"
echo "  $OUT_DIR"
echo ""
echo "Boss runs (after docker load):"
echo "  HOST_DATA_DIR=/his/path docker compose -f docker-compose.boss.yml up -d"
