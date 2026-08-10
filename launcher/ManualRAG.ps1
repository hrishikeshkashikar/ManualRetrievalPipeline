# Manual RAG — Edge query-only launcher (PowerShell)
# Requires Docker Desktop + Ollama once. Prefer ManualRAG.exe for double-click.

param(
    [string]$DataDir = "",
    [string]$Port = "8000",
    [string]$ImageTar = "manual-rag-query.tar.gz",
    [string]$ImageTag = "manual-rag-query:latest",
    [string]$ComposeFile = "docker-compose.edge.yml",
    [string]$VisionModel = "qwen2.5vl:3b"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (Test-Path "..\$ComposeFile") { Set-Location .. }

Write-Host ""
Write-Host " ========================================================"
Write-Host "  Manual RAG — Edge Query-Only"
Write-Host " ========================================================"
Write-Host ""

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker is not installed. Install Docker Desktop first:"
    Write-Host "  https://www.docker.com/products/docker-desktop/"
    exit 1
}

try { docker info | Out-Null } catch {
    Write-Host "Docker Desktop is not running. Start it and retry."
    exit 1
}

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama is not installed. Install once (needs internet):"
    Write-Host "  https://ollama.com/download"
    exit 1
}

try {
    Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
} catch {
    Write-Host "Starting Ollama..."
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        try {
            Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        } catch {}
    }
    if (-not $ready) {
        Write-Host "Ollama is not responding. Open the Ollama app and retry."
        exit 1
    }
}

$tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10
$names = @()
if ($tags.models) { $names = $tags.models | ForEach-Object { $_.name } }
if ($names -notcontains $VisionModel) {
    Write-Host "Pulling $VisionModel (one-time; needs internet)..."
    ollama pull $VisionModel
    Write-Host "Model ready — later runs can be air-gapped."
} else {
    Write-Host "Host model $VisionModel present."
}

if (-not (Test-Path $ComposeFile)) {
    Write-Host "Missing $ComposeFile in $(Get-Location)"
    exit 1
}

if (-not $DataDir) {
    $DataDir = Read-Host "Enter path to data folder (chroma_db + images + manuals)"
}
if (-not $DataDir -or -not (Test-Path $DataDir)) {
    Write-Host "Invalid data path: $DataDir"
    exit 1
}

$imgOk = $true
try { docker image inspect $ImageTag | Out-Null } catch { $imgOk = $false }
if (-not $imgOk) {
    if (-not (Test-Path $ImageTar)) {
        Write-Host "Image $ImageTag not loaded and $ImageTar missing."
        exit 1
    }
    Write-Host "Loading $ImageTar (first run can take several minutes)..."
    docker load -i $ImageTar
}

$env:HOST_DATA_DIR = (Resolve-Path $DataDir).Path
$env:API_PORT = $Port
$env:EDGE_IMAGE = $ImageTag
$env:OLLAMA_VISION_MODEL = $VisionModel

Write-Host "Starting container..."
docker compose -f $ComposeFile up -d

$wait = 0
while ($wait -lt 180) {
    $status = docker inspect --format='{{.State.Health.Status}}' manual-rag-edge 2>$null
    if ($status -eq "healthy") { break }
    Start-Sleep -Seconds 5
    $wait += 5
    Write-Host "  ... ${wait}s — $status"
}

$url = "http://localhost:$Port/"
Write-Host "Opening $url"
Start-Process $url
Write-Host "Stop later: docker compose -f $ComposeFile down"
