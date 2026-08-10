#!/usr/bin/env bash
# Build ManualRAG.app and ManualRAG.dmg for macOS (same role as ManualRAG.exe).
#
# Usage (from repo root):
#   ./scripts/build_mac_dmg.sh
#   ./scripts/build_mac_dmg.sh --with-compose   # copy docker-compose.edge.yml into DMG
#   ./scripts/build_mac_dmg.sh --with-image ./manual-rag-query.tar.gz
#
# The DMG is a thin launcher package. The Docker image can be:
#   - already loaded as manual-rag-query:latest, or
#   - included via --with-image (makes the DMG multi-GB)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WITH_COMPOSE=true
IMAGE_TAR=""
OUT_DMG="$ROOT/launcher/ManualRAG.dmg"
STAGE="$ROOT/launcher/.dmg-stage"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-compose) WITH_COMPOSE=true; shift ;;
    --no-compose) WITH_COMPOSE=false; shift ;;
    --with-image) IMAGE_TAR="$2"; shift 2 ;;
    --out) OUT_DMG="$2"; shift 2 ;;
    --help|-h) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "Unknown: $1" >&2; exit 1 ;;
  esac
done

if ! command -v go >/dev/null 2>&1; then
  echo "✗ Go not found. Install: brew install go"
  exit 1
fi

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Build ManualRAG.dmg (macOS launcher)                   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Native macOS binary ────────────────────────────────────────────────────
ARCH="$(uname -m)"
echo "▸ Building darwin/${ARCH} binary..."
(
  cd launcher
  CGO_ENABLED=0 go build -ldflags="-s -w" -o ManualRAG-darwin .
)

# ── App bundle ─────────────────────────────────────────────────────────────
APP="$ROOT/launcher/ManualRAG.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cp launcher/ManualRAG-darwin "$APP/Contents/MacOS/ManualRAG"
chmod +x "$APP/Contents/MacOS/ManualRAG"

# Simple icon-less Info.plist (system default app icon)
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>ManualRAG</string>
  <key>CFBundleDisplayName</key>
  <string>Manual RAG</string>
  <key>CFBundleIdentifier</key>
  <string>local.manualrag.edge-launcher</string>
  <key>CFBundleVersion</key>
  <string>1.0.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundleExecutable</key>
  <string>ManualRAG</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

# ── DMG staging folder ─────────────────────────────────────────────────────
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/ManualRAG.app"

if [[ "$WITH_COMPOSE" == true ]]; then
  cp docker-compose.edge.yml "$STAGE/"
fi

cat > "$STAGE/README.txt" <<'EOF'
Manual RAG — macOS Edge Launcher
================================

Same flow as ManualRAG.exe on Windows:
  Docker → check Ollama → pull qwen2.5vl:3b if missing → pick data/ → open UI

One-time (needs internet once)
------------------------------
1. Install Docker Desktop and start it.
2. Install Ollama and open it once: https://ollama.com/download
3. Have the thin query image ready:
     ./scripts/build.sh --edge --export
   Then either load it, or put manual-rag-query.tar.gz next to ManualRAG.app
   (copy app + compose + tar out of this DMG onto a writable folder first).

Every time
----------
1. Copy ManualRAG.app + docker-compose.edge.yml to a writable folder
   (do not run only from the read-only DMG volume long-term).
2. Right-click ManualRAG.app → Open → Open  (first time only).
3. App checks Ollama; pulls qwen2.5vl:3b if missing.
4. macOS folder picker → select prebuilt data/
   (must contain chroma_db/, images/, manuals/).
5. Browser opens http://localhost:8000/

Stop
----
  docker compose -f docker-compose.edge.yml down

After the model pull, later runs can be air-gapped.
EOF

if [[ -n "$IMAGE_TAR" ]]; then
  if [[ ! -f "$IMAGE_TAR" ]]; then
    echo "✗ Image tar not found: $IMAGE_TAR"
    exit 1
  fi
  echo "▸ Including image tar (DMG will be large)..."
  cp "$IMAGE_TAR" "$STAGE/manual-rag-query.tar.gz"
fi

# ── Create DMG ─────────────────────────────────────────────────────────────
echo "▸ Creating DMG..."
rm -f "$OUT_DMG"
hdiutil create \
  -volname "ManualRAG" \
  -srcfolder "$STAGE" \
  -ov \
  -format UDZO \
  "$OUT_DMG" >/dev/null

rm -rf "$STAGE"

echo ""
echo "✓ App : $APP"
echo "✓ DMG : $OUT_DMG ($(du -h "$OUT_DMG" | awk '{print $1}'))"
echo ""
echo "Open with: open \"$OUT_DMG\""
echo ""
