# Shared helpers. Dot-source from the other scripts: . "$PSScriptRoot\_common.ps1"
# Not 'Stop': in Windows PowerShell 5.1 any stderr line from docker/pip/npm would abort the script.
# Failures are checked with $LASTEXITCODE and throw instead.
$ErrorActionPreference = 'Continue'

$Root     = Split-Path $PSScriptRoot -Parent
$PyDir    = Join-Path $Root 'python'
$WebDir   = Join-Path $Root 'frontend'
$VenvPy   = Join-Path $PyDir '.venv\Scripts\python.exe'
$PidDir   = Join-Path $PSScriptRoot '.pids'
$ApiUrl   = 'http://127.0.0.1:8000'

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host "    $msg" -ForegroundColor Yellow }

function Test-Backend {
    try {
        $r = Invoke-WebRequest -Uri "$ApiUrl/docs" -UseBasicParsing -TimeoutSec 2
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

function Assert-Venv {
    if (-not (Test-Path $VenvPy)) {
        throw "python\.venv not found. Run: setup"
    }
}

# Kill a process and its children (uvicorn --reload spawns a child).
function Stop-Tree($procId) {
    if ($procId) { & taskkill.exe /PID $procId /T /F *> $null }
}

# Kill whatever still listens on a TCP port.
function Stop-Port($port) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) { Stop-Tree $c.OwningProcess }
}

# Open a tab in the shared Windows Terminal window "driftpulse" (separate window if wt is missing).
# Default: tracked tab for start/stop. The shell PID goes to .pids\<name>; the command runs as a
# child and the shell then exits 0, so stop-all can kill only the child and the tab closes itself.
# -KeepOpen: untracked tab that stays open after the command ends, so the output can be read.
function Start-Tab($name, $workDir, $command, [switch]$KeepOpen) {
    $inner = "`$host.UI.RawUI.WindowTitle='DriftPulse $name'; "
    if (-not $KeepOpen) {
        New-Item -ItemType Directory -Force $PidDir | Out-Null
        $inner += "`$PID | Set-Content '$(Join-Path $PidDir $name)'; "
    }
    $inner += "Set-Location '$workDir'; $command"
    if (-not $KeepOpen) { $inner += '; exit 0' }
    $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($inner))
    $psExe = Join-Path $PSHOME 'powershell.exe'
    $shellArgs = @('-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass')
    if ($KeepOpen) { $shellArgs += '-NoExit' }
    $shellArgs += @('-EncodedCommand', $enc)
    if (Get-Command wt.exe -ErrorAction SilentlyContinue) {
        Start-Process wt.exe -ArgumentList (@('-w', 'driftpulse', 'new-tab', '--title', "`"DriftPulse $name`"",
            '--suppressApplicationTitle', '-d', "`"$workDir`"", "`"$psExe`"") + $shellArgs)
    } else {
        Start-Process $psExe -ArgumentList ($shellArgs + '-NoExit')
    }
}
