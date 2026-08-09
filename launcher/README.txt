Manual RAG — Launchers
======================

Windows
-------
ManualRAG.exe   Thin double-click launcher (requires Docker Desktop)
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
2. Double-click ManualRAG.exe (Windows) or ManualRAG.app (macOS from DMG)
3. Enter / pick the prebuilt data/ folder
4. Browser opens http://localhost:8000/

Place docker-compose.edge.yml (and optionally manual-rag-query.tar.gz)
next to the launcher in the edge bundle.
