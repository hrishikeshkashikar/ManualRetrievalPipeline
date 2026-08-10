@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Manual RAG — Edge Query Launcher

REM Thin launcher: Docker + host Ollama. Vision model is NOT in the Docker image.
REM Double-click this file (or ManualRAG.exe if built) on the edge PC.

cd /d "%~dp0"
if exist "%~dp0..\docker-compose.edge.yml" (
  cd /d "%~dp0.."
)

set "COMPOSE_FILE=docker-compose.edge.yml"
set "IMAGE_TAR=manual-rag-query.tar.gz"
set "IMAGE_TAG=manual-rag-query:latest"
set "PORT=8000"
set "VISION_MODEL=qwen2.5vl:3b"

echo.
echo  ========================================================
echo   Manual RAG — Edge Query-Only
echo  ========================================================
echo.

where docker >nul 2>&1
if errorlevel 1 (
  echo  Docker is not installed or not on PATH.
  echo  Install Docker Desktop, start it, then run this again:
  echo    https://www.docker.com/products/docker-desktop/
  echo.
  pause
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo  Docker Desktop is installed but not running.
  echo  Start Docker Desktop, wait until it is ready, then retry.
  echo.
  pause
  exit /b 1
)

where ollama >nul 2>&1
if errorlevel 1 (
  echo  Ollama is not installed.
  echo  Install once (needs internet), then re-run:
  echo    https://ollama.com/download
  echo.
  pause
  exit /b 1
)

curl -sf http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
  echo  Starting Ollama...
  start "" /b ollama serve
  set /a OWAIT=0
  :ollama_wait
  curl -sf http://127.0.0.1:11434/api/tags >nul 2>&1
  if not errorlevel 1 goto ollama_ready
  set /a OWAIT+=1
  if %OWAIT% GEQ 30 (
    echo  Ollama is not responding. Open the Ollama app and retry.
    pause
    exit /b 1
  )
  timeout /t 1 /nobreak >nul
  goto ollama_wait
)
:ollama_ready
echo  Ollama API ready.

ollama list 2>nul | findstr /i "%VISION_MODEL%" >nul
if errorlevel 1 (
  echo  Pulling %VISION_MODEL% (one-time; needs internet)...
  ollama pull %VISION_MODEL%
  if errorlevel 1 (
    echo  Failed to pull model. Connect to the internet once and retry.
    pause
    exit /b 1
  )
  echo  Model ready — later runs can be air-gapped.
) else (
  echo  Host model %VISION_MODEL% present.
)

if not exist "%COMPOSE_FILE%" (
  echo  Missing %COMPOSE_FILE% in:
  echo    %CD%
  echo  Copy the edge bundle folder intact and try again.
  echo.
  pause
  exit /b 1
)

set "DATA_DIR="
if not "%~1"=="" (
  set "DATA_DIR=%~1"
) else (
  set /p DATA_DIR=Enter path to data folder (chroma_db + images + manuals): 
)

if "%DATA_DIR%"=="" (
  echo  No data path provided.
  pause
  exit /b 1
)

if not exist "%DATA_DIR%" (
  echo  Path not found: %DATA_DIR%
  pause
  exit /b 1
)

echo.
echo  Data : %DATA_DIR%
echo.

REM Load image if present and not already loaded
docker image inspect %IMAGE_TAG% >nul 2>&1
if errorlevel 1 (
  if exist "%IMAGE_TAR%" (
    echo  Loading Docker image from %IMAGE_TAR% ...
    echo  This can take several minutes on first run.
    docker load -i "%IMAGE_TAR%"
    if errorlevel 1 (
      echo  Failed to load image.
      pause
      exit /b 1
    )
  ) else (
    echo  Image %IMAGE_TAG% not found and %IMAGE_TAR% missing.
    echo  Place the exported tar.gz in this folder, or build with:
    echo    ./scripts/build.sh --edge --export
    pause
    exit /b 1
  )
)

set "HOST_DATA_DIR=%DATA_DIR%"
set "API_PORT=%PORT%"
set "EDGE_IMAGE=%IMAGE_TAG%"
set "OLLAMA_VISION_MODEL=%VISION_MODEL%"

echo  Starting query-only container...
docker compose -f "%COMPOSE_FILE%" up -d
if errorlevel 1 (
  echo  Failed to start. Check Docker logs.
  pause
  exit /b 1
)

echo  Waiting for health...
set /a WAIT=0
:wait_loop
docker inspect --format="{{.State.Health.Status}}" manual-rag-edge 2>nul | findstr /i "healthy" >nul
if not errorlevel 1 goto ready
set /a WAIT+=5
if %WAIT% GEQ 180 goto ready
timeout /t 5 /nobreak >nul
echo   ... %WAIT%s
goto wait_loop

:ready
echo.
echo  Opening http://localhost:%PORT%/
start "" "http://localhost:%PORT%/"
echo.
echo  Stop later with:
echo    docker compose -f %COMPOSE_FILE% down
echo.
pause
endlocal
