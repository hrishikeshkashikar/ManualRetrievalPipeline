#!/usr/bin/env bash
# Package the thin query-only edge image + launcher for boss / edge machine.
# Vision model is NOT in the tar — host Ollama pulls it once (needs internet).
# data/ is always mounted at runtime (never baked into the image).
#
# Usage:
#   ./scripts/export_for_edge.sh
#   ./scripts/export_for_edge.sh --image manual-rag-query:latest --with-data /path/to/data

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

IMAGE_TAG="manual-rag-query:latest"
DATA_SRC=""
OUT_DIR="$ROOT/exports/manual-rag-edge-bundle"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image) IMAGE_TAG="$2"; shift 2 ;;
    --with-data) DATA_SRC="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    --help|-h) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown: $1" >&2; exit 1 ;;
  esac
done

if ! docker image inspect "$IMAGE_TAG" >/dev/null 2>&1; then
  echo "✗ Image '$IMAGE_TAG' not found. Build first:"
  echo "    ./scripts/build.sh --edge"
  exit 1
fi

IMAGE_SIZE=$(docker image inspect "$IMAGE_TAG" --format='{{.Size}}' | awk '{printf "%.2f GB", $1/1073741824}')

mkdir -p "$OUT_DIR"
TAR="$OUT_DIR/manual-rag-query.tar.gz"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Export edge / boss bundle (thin + host Ollama)          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo "  Image : $IMAGE_TAG ($IMAGE_SIZE)"
echo "  Out   : $OUT_DIR"
echo ""

echo "▸ Saving image..."
docker save "$IMAGE_TAG" | gzip -1 > "$TAR"
TAR_SIZE=$(du -h "$TAR" | awk '{print $1}')
echo "  ✓ $TAR ($TAR_SIZE compressed)"

cp docker-compose.edge.yml "$OUT_DIR/"
cp scripts/load_and_run_edge.sh "$OUT_DIR/"
chmod +x "$OUT_DIR/load_and_run_edge.sh"

mkdir -p "$OUT_DIR/launcher"
cp launcher/ManualRAG.bat "$OUT_DIR/launcher/" 2>/dev/null || true
cp launcher/ManualRAG.ps1 "$OUT_DIR/launcher/" 2>/dev/null || true
cp launcher/README.txt "$OUT_DIR/launcher/" 2>/dev/null || true
if [[ -f launcher/ManualRAG.exe ]]; then
  cp launcher/ManualRAG.exe "$OUT_DIR/"
fi
cp launcher/ManualRAG.bat "$OUT_DIR/" 2>/dev/null || true
if [[ -f launcher/ManualRAG.dmg ]]; then
  cp launcher/ManualRAG.dmg "$OUT_DIR/"
fi
if [[ -d launcher/ManualRAG.app ]]; then
  rm -rf "$OUT_DIR/ManualRAG.app"
  cp -R launcher/ManualRAG.app "$OUT_DIR/"
fi

if [[ -n "$DATA_SRC" ]]; then
  echo "▸ Copying sample data from $DATA_SRC (separate from image)..."
  mkdir -p "$OUT_DIR/sample-data"
  rsync -a --delete \
    --exclude '.DS_Store' \
    "$DATA_SRC/" "$OUT_DIR/sample-data/" 2>/dev/null \
    || cp -R "$DATA_SRC/." "$OUT_DIR/sample-data/"
fi

cat > "$OUT_DIR/README-BOSS.txt" <<'EOF'
Manual RAG — Edge Query-Only (Windows / macOS / low RAM)
========================================================

What this is
------------
Thin Docker app for query-only use on ~8 GB RAM machines.
The vision model runs on host Ollama (faster, uses CPU/GPU natively).
Ingest PDFs on a stronger PC first, then copy the data/ folder here.

One-time setup (needs internet once)
------------------------------------
1) Install Docker Desktop and start it.
   https://www.docker.com/products/docker-desktop/
2) Install Ollama and start it.
   https://ollama.com/download
3) First launch will pull qwen2.5vl:3b if missing.
   After that, the PC can stay air-gapped.

Every time
----------
Option A — Windows:
  1. Put this whole folder on the PC or USB.
  2. Double-click ManualRAG.exe (or ManualRAG.bat).
  3. Enter the path to your data folder
     (must contain chroma_db/, images/, manuals/).
  4. Browser opens at http://localhost:8000/

Option B — macOS:
  1. Open ManualRAG.dmg (or use ManualRAG.app in this folder).
  2. First time: Right-click ManualRAG.app → Open → Open.
  3. Pick your data folder in the macOS dialog.
  4. Browser opens at http://localhost:8000/
  Keep docker-compose.edge.yml next to the .app.

Option C — Command line:
  ./load_and_run_edge.sh --image manual-rag-query.tar.gz --data /path/to/data

Notes
-----
- The Docker image does NOT include the vision model or your data/.
- data/ is always mounted from a path you choose.
- No ingest on this machine — Upload is hidden in the UI.
- Stop: docker compose -f docker-compose.edge.yml down
EOF

echo ""
echo "✓ Bundle ready:"
du -sh "$OUT_DIR"/* 2>/dev/null | sed 's/^/  /'
echo ""
echo "  $OUT_DIR"
echo "  Image layer size (uncompressed): $IMAGE_SIZE"
echo "  Tar compressed: $TAR_SIZE"
echo ""
echo "  Client still needs: Docker + Ollama + one-time model pull + data/ path"
