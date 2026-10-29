$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Stop-WithHelp([string]$message) {
    Write-Host "`n$message" -ForegroundColor Red
    exit 1
}

Write-Host "`nPharmind local workspace" -ForegroundColor Cyan
Write-Host "First launch downloads app dependencies and local embedding/reranking models. Research runs locally by default. Optional cloud providers are configured in the app."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Stop-WithHelp "Docker was not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop/ and start it, then double-click start-pharmer.bat again."
}
$backendEnv = Join-Path $root "backend\.env"
if (-not (Test-Path $backendEnv)) {
    $exampleEnv = Join-Path $root "backend\.env.example"
    if (Test-Path $exampleEnv) {
        Copy-Item $exampleEnv $backendEnv
        Write-Host "Created backend\.env from backend\.env.example" -ForegroundColor Green
    }
}
$provider = "ollama"
if (Test-Path $backendEnv) {
    $providerLine = Select-String -Path $backendEnv -Pattern '^\s*LLM_PROVIDER\s*=\s*(.+?)\s*$' | Select-Object -Last 1
    if ($providerLine) { $provider = $providerLine.Matches[0].Groups[1].Value.Trim('"', "'").ToLowerInvariant() }
}

docker compose version *> $null
if ($LASTEXITCODE -ne 0) { Stop-WithHelp "Docker Compose is unavailable. Update or reinstall Docker Desktop, then try again." }
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $dockerDesktop = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerDesktop) {
        Write-Host "Starting Docker Desktop..."
        Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
        $ready = $false
        for ($i = 0; $i -lt 60; $i++) {
            Start-Sleep -Seconds 2
            docker info *> $null
            if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        }
        if (-not $ready) { Stop-WithHelp "Docker Desktop did not become ready. Open Docker Desktop, wait until it says it is running, then try again." }
    } else {
        Stop-WithHelp "Docker is installed but not running. Open Docker Desktop, wait until it says it is running, then try again."
    }
}

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "Ollama detected. Select a downloaded model in the app connection settings."
} else {
    Write-Host "Install Ollama for local inference, or bring your provider key in the app connection settings."
}

Write-Host "Building and starting the local Pharmer app..."
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { Stop-WithHelp "The app could not build or start. Check Docker Desktop and disk space, then run this launcher again." }

$apiReady = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 2
    try { $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 3; $apiReady = $true; break } catch {}
}
if (-not $apiReady) { Stop-WithHelp "The local API is still starting or failed. Run stop-pharmer.bat, then try again. If it repeats, share the Docker Desktop logs with the project maintainer." }

Write-Host "Preparing local document models (downloads once, then uses the cache)..."
docker compose exec -T backend python scripts/prepare_local_models.py
if ($LASTEXITCODE -ne 0) { Stop-WithHelp "Local model preparation failed. Connect to the internet for the initial download, then retry." }

Write-Host "`nPharmind is ready at http://localhost:3000" -ForegroundColor Green
Write-Host "Choose Ollama or your own provider key in connection settings. Add PDFs to start your local library."
Start-Process "http://localhost:3000"
