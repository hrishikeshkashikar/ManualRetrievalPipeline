#!/usr/bin/env bash
# Package the query-only edge image + launcher for boss / edge machine.
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
    --help|-h) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "Unknown: $1" >&2; exit 1 ;;
  esac
done

if ! docker image inspect "$IMAGE_TAG" >/dev/null 2>&1; then
  echo "✗ Image '$IMAGE_TAG' not found. Build first:"
  echo "    ./scripts/build.sh --edge"
  exit 1
fi

mkdir -p "$OUT_DIR"
TAR="$OUT_DIR/manual-rag-query.tar.gz"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Export edge / boss bundle                               ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo "  Image : $IMAGE_TAG"
echo "  Out   : $OUT_DIR"
echo ""

echo "▸ Saving image (several minutes)..."
docker save "$IMAGE_TAG" | gzip -1 > "$TAR"

cp docker-compose.edge.yml "$OUT_DIR/"
cp scripts/load_and_run_edge.sh "$OUT_DIR/"
chmod +x "$OUT_DIR/load_and_run_edge.sh"

mkdir -p "$OUT_DIR/launcher"
cp launcher/ManualRAG.bat "$OUT_DIR/launcher/" 2>/dev/null || true
cp launcher/ManualRAG.ps1 "$OUT_DIR/launcher/" 2>/dev/null || true
cp launcher/README.txt "$OUT_DIR/launcher/" 2>/dev/null || true
# Prefer a prebuilt exe if present — also copy bat to bundle root for double-click
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
  echo "▸ Copying sample data from $DATA_SRC ..."
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
Query-only deployment for ~8 GB RAM machines.
Ingest PDFs on a stronger PC first, then copy the data/ folder here.

One-time setup
--------------
1) Install Docker Desktop and start it.
   https://www.docker.com/products/docker-desktop/

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
  Keep docker-compose.edge.yml next to the .app (already true in this bundle).

Option C — Command line:
  ./load_and_run_edge.sh --image manual-rag-query.tar.gz --data /path/to/data

Notes
-----
- First start loads the image (can take several minutes) if not already loaded.
- No ingest on this machine — Upload is hidden in the UI.
- Stop: docker compose -f docker-compose.edge.yml down
EOF

echo ""
echo "✓ Bundle ready:"
du -sh "$OUT_DIR"/* 2>/dev/null | sed 's/^/  /'
echo ""
echo "  $OUT_DIR"
