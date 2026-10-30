$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$composeArgs = @("compose", "--project-name", "pharmind-local", "--file", (Join-Path $root "docker-compose.yml"))
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker was not found. Install Docker Desktop to stop the Pharmind Local containers." -ForegroundColor Red
    exit 1
}
docker @composeArgs down
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Pharmind Local is stopped. Your local index and model downloads are kept. Ollama is left running." -ForegroundColor Green
