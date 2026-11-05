# Start Docker (PostgreSQL), backend and frontend. Backend and frontend each get their own window.
# Old windows from a previous run are closed first. Database data is kept.
param(
    [switch]$NoFrontend,
    [switch]$NoDocker
)
. "$PSScriptRoot\_common.ps1"
Assert-Venv

Write-Step 'Closing old backend/frontend windows'
& "$PSScriptRoot\stop-all.ps1"

if (-not $NoDocker) {
    Write-Step 'Docker: PostgreSQL'
    Push-Location $Root
    & docker compose up -d
    Pop-Location
    if ($LASTEXITCODE -ne 0) { throw 'docker compose failed. Is Docker Desktop running?' }
    for ($i = 0; $i -lt 40; $i++) {
        $h = & docker inspect -f '{{.State.Health.Status}}' driftpulse-postgres 2>$null
        if ($h -eq 'healthy') { break }
        Start-Sleep -Seconds 2
    }
    if ($h -ne 'healthy') { throw "postgres not healthy (status: $h)" }
    Write-Ok 'postgres healthy'
}

Write-Step 'Backend tab'
Start-Tab 'Backend' $PyDir "& '$VenvPy' -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000"

if (-not $NoFrontend) {
    Start-Sleep -Seconds 2
    Write-Step 'Frontend tab'
    Start-Tab 'Frontend' $WebDir 'npm.cmd run dev'
}

Write-Step 'Waiting for backend'
$up = $false
for ($i = 0; $i -lt 60; $i++) {
    if (Test-Backend) { $up = $true; break }
    Start-Sleep -Seconds 1
}
if ($up) { Write-Ok "backend up: $ApiUrl/docs" }
else     { Write-Warn2 'backend not answering yet. Check the Backend window for errors.' }

if (-not $NoFrontend) { Write-Ok 'dashboard: http://localhost:5173' }
Write-Host ''
Write-Host 'Next: data   (sensor or simulation)' -ForegroundColor Green
