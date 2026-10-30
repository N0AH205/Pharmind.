$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$composeArgs = @("compose", "--project-name", "pharmind-local", "--file", (Join-Path $root "docker-compose.yml"))

function Stop-WithHelp([string]$message) {
    Write-Host "`n$message" -ForegroundColor Red
    exit 1
}

Write-Host "`nPharmind Local workspace" -ForegroundColor Cyan
Write-Host "First launch downloads app dependencies and local embedding/reranking models. Research runs locally by default. Optional cloud providers are configured in the app."
Write-Host "Ollama and the model that writes answers must be installed separately on your computer."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Stop-WithHelp "Docker was not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop/ and start it, then double-click start-pharmind-local.bat again."
}
$backendEnv = Join-Path $root "backend\.env"
if (-not (Test-Path $backendEnv)) {
    $exampleEnv = Join-Path $root "backend\.env.example"
    if (Test-Path $exampleEnv) {
        Copy-Item $exampleEnv $backendEnv
        Write-Host "Created backend\.env from backend\.env.example" -ForegroundColor Green
    }
}
docker @composeArgs version *> $null
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

Write-Host "Building and starting Pharmind Local..."
docker @composeArgs up -d --build
if ($LASTEXITCODE -ne 0) { Stop-WithHelp "The app could not build or start. Check Docker Desktop and disk space, then run this launcher again." }

$apiReady = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 2
    try { $health = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -TimeoutSec 3; $apiReady = $true; break } catch {}
}
if (-not $apiReady) { Stop-WithHelp "The local API is still starting or failed. Run stop-pharmind-local.bat, then try again. If it repeats, share the Docker Desktop logs with the project maintainer." }

try {
    $modelRequest = @{ provider = "ollama"; base_url = "http://localhost:11434" } | ConvertTo-Json -Compress
    $localModels = Invoke-RestMethod -Uri "http://127.0.0.1:8001/connection/ollama-models" -Method Post -ContentType "application/json" -Body $modelRequest -TimeoutSec 15
    $answerModels = @($localModels.models | Where-Object { $_.can_chat -ne $false })
    if ($answerModels.Count -eq 0) {
        Write-Host "Ollama has no available answer models. Run ollama pull qwen2.5:3b, then refresh models in the app."
    } else {
        Write-Host ("Installed Ollama models: " + (($answerModels | ForEach-Object { $_.name }) -join ", "))
        if (-not ($answerModels | Where-Object { $_.name -eq "qwen2.5:3b" })) {
            Write-Host "The app's default qwen2.5:3b model is not installed. Choose an installed model in Model & connection and save it."
        }
    }
} catch {
    Write-Host "Ollama could not be checked. Install/start Ollama for local answers, or choose a BYOK provider in Model & connection."
}

Write-Host "Preparing local document models (downloads once, then uses the cache)..."
docker @composeArgs exec -T backend python scripts/prepare_local_models.py
if ($LASTEXITCODE -ne 0) { Stop-WithHelp "Local model preparation failed. Connect to the internet for the initial download, then retry." }

Write-Host "`nPharmind Local is ready at http://localhost:3001" -ForegroundColor Green
Write-Host "Choose Ollama or your own provider key in connection settings. Add PDFs to start your local library."
Start-Process "http://localhost:3001"
