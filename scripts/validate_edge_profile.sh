#!/usr/bin/env bash
# Validate the edge query-only profile without needing an 8GB box.
#
# Checks:
#   1) Settings resolve correctly for QUERY_ONLY / low-RAM env
#   2) docker-compose.edge.yml points at host Ollama
#   3) Dockerfile.edge is thin (no ollama bake)
#   4) Launcher artifacts exist (bat / exe)
#   5) Unit tests for the edge profile
#
# Full hardware soak (cold start + one query on real data/) still needs
# the edge machine + prebuilt knowledge base + host Ollama.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Edge profile validation                                 ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── 1) Settings ────────────────────────────────────────────────────────────
PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

QUERY_ONLY=true ENABLE_RERANKER=false OLLAMA_NUM_CTX=8192 MAX_GENERATION_IMAGES=1 \
"$PYTHON" - <<'PY'
from app.config import Settings
s = Settings()
assert s.query_only is True, s
assert s.enable_reranker is False, s
assert s.ollama_num_ctx == 8192, s
assert s.max_generation_images == 1, s
print("✓ Settings: query_only / no-reranker / num_ctx=8192 / max_images=1")
PY

# ── 2) Compose + thin Dockerfile ───────────────────────────────────────────
grep -q 'host.docker.internal:11434' docker-compose.edge.yml
grep -q 'QUERY_ONLY=true' docker-compose.edge.yml
echo "✓ docker-compose.edge.yml uses host Ollama + QUERY_ONLY"

test -f Dockerfile.edge
! grep -q 'FROM ollama/ollama' Dockerfile.edge
grep -q 'QUERY_ONLY=true' Dockerfile.edge
echo "✓ Dockerfile.edge is thin (no ollama/ollama stage)"

test -f requirements.edge.txt
! grep -qi 'PyMuPDF' requirements.edge.txt
echo "✓ requirements.edge.txt omits PyMuPDF"

if command -v docker >/dev/null 2>&1; then
  docker compose -f docker-compose.edge.yml config >/dev/null
  echo "✓ docker-compose.edge.yml parses"
else
  echo "⚠ docker not available — skipped compose parse"
fi

# ── 3) Launcher artifacts ──────────────────────────────────────────────────
test -f launcher/ManualRAG.bat && echo "✓ launcher/ManualRAG.bat"
test -f launcher/ManualRAG.ps1 && echo "✓ launcher/ManualRAG.ps1"
if grep -q 'ensureOllama\|ollama.com/download' launcher/main.go; then
  echo "✓ launcher/main.go checks host Ollama"
else
  echo "✗ launcher/main.go missing Ollama ensure logic"
  exit 1
fi
if [[ -f launcher/ManualRAG.exe ]]; then
  echo "✓ launcher/ManualRAG.exe ($(du -h launcher/ManualRAG.exe | awk '{print $1}'))"
else
  echo "⚠ launcher/ManualRAG.exe missing — build with:"
  echo "    cd launcher && GOOS=windows GOARCH=amd64 go build -o ManualRAG.exe ."
fi
if [[ -f launcher/ManualRAG.dmg ]]; then
  echo "✓ launcher/ManualRAG.dmg ($(du -h launcher/ManualRAG.dmg | awk '{print $1}'))"
else
  echo "⚠ launcher/ManualRAG.dmg missing — build with: ./scripts/build_mac_dmg.sh"
fi
if [[ -d launcher/ManualRAG.app ]]; then
  echo "✓ launcher/ManualRAG.app"
fi
test -f scripts/load_and_run_edge.sh && echo "✓ scripts/load_and_run_edge.sh"
test -f scripts/export_for_edge.sh && echo "✓ scripts/export_for_edge.sh"

# ── 4) Unit tests ──────────────────────────────────────────────────────────
if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  "${ROOT}/.venv/bin/python" -m pytest tests/test_edge_profile.py -q --tb=line
  echo "✓ Edge unit tests passed"
else
  echo "⚠ .venv missing — skipped pytest (run: python -m pytest tests/test_edge_profile.py)"
fi

echo ""
echo "Hardware soak (on 8GB edge box with prebuilt data/):"
echo "  1. ./scripts/build.sh --edge --export"
echo "  2. ./scripts/export_for_edge.sh"
echo "  3. On edge: install Docker + Ollama; double-click ManualRAG.exe; point at data/"
echo "  4. Confirm /health shows query_only=true, ollama_connected=true"
echo "  5. Run one chat query; container RAM should stay far below the old all-in-one image"
echo ""
