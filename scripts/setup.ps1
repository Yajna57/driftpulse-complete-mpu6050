# One-time setup. Safe to re-run: finished steps are skipped.
. "$PSScriptRoot\_common.ps1"

Write-Step 'Checking tools'
foreach ($tool in 'docker', 'node', 'npm', 'py') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool not found on PATH" }
}
& py -3.14 --version
if ($LASTEXITCODE -ne 0) { throw 'Python 3.14 not found (py -3.14)' }

Write-Step 'Python venv'
if (-not (Test-Path $VenvPy)) {
    Push-Location $PyDir
    & py -3.14 -m venv .venv
    Pop-Location
    Write-Ok 'venv created'
} else { Write-Ok 'venv exists' }
& $VenvPy -m pip install --upgrade pip setuptools wheel
& $VenvPy -m pip install -r (Join-Path $PyDir 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }

Write-Step '.env files'
foreach ($dir in $PyDir, $WebDir) {
    $env1 = Join-Path $dir '.env'
    if (-not (Test-Path $env1)) {
        Copy-Item (Join-Path $dir '.env.example') $env1
        Write-Ok "created $env1"
    } else { Write-Ok "kept $env1" }
}

Write-Step 'Frontend packages'
if (-not (Test-Path (Join-Path $WebDir 'node_modules'))) {
    Push-Location $WebDir
    & npm.cmd install
    Pop-Location
    if ($LASTEXITCODE -ne 0) { throw 'npm install failed' }
} else { Write-Ok 'node_modules exists' }

Write-Host ''
Write-Host 'Setup done. Next: start' -ForegroundColor Green
