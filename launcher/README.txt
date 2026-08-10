Manual RAG — Launchers
======================

Windows
-------
ManualRAG.exe   Thin double-click launcher (Docker + host Ollama)
ManualRAG.bat   Same flow without compiling
ManualRAG.ps1   PowerShell variant

Build Windows exe:
  cd launcher
  GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o ManualRAG.exe .

macOS
-----
ManualRAG.app   Double-click app (folder picker via macOS dialog)
ManualRAG.dmg   Disk image containing the app + compose + README

Build DMG:
  ./scripts/build_mac_dmg.sh
  ./scripts/build_mac_dmg.sh --with-image ./manual-rag-query.tar.gz

Boss / edge experience
----------------------
1. Install Docker Desktop once
2. Install Ollama once (https://ollama.com/download)
3. Double-click ManualRAG.exe (Windows) or ManualRAG.app (macOS from DMG)
   — first run pulls qwen2.5vl:3b if missing (needs internet once)
4. Enter / pick the prebuilt data/ folder
5. Browser opens http://localhost:8000/

After the model pull, the machine can stay air-gapped.

Place docker-compose.edge.yml (and optionally manual-rag-query.tar.gz)
next to the launcher in the edge bundle. The vision model is NOT inside
the Docker tar — it lives in host Ollama.
