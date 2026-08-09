# Manual RAG — Edge query-only launcher (PowerShell)
# Requires Docker Desktop once. Prefer ManualRAG.bat for double-click,
# or compile launcher/main.go to ManualRAG.exe on a machine with Go.

param(
    [string]$DataDir = "",
    [string]$Port = "8000",
    [string]$ImageTar = "manual-rag-query.tar.gz",
    [string]$ImageTag = "manual-rag-query:latest",
    [string]$ComposeFile = "docker-compose.edge.yml"
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
