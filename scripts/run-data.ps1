# Feed data into the running backend: real Arduino sensor OR simulation.
# Run it as often as you like. Any option left out is asked at run time.
#   data                                  -> interactive menu
#   data -Mode sim -Case 7                -> simulation case 7
#   data -Mode sim -Case all              -> cases 1..10 one after another
#   data -Mode sim -List                  -> list cases
#   data -Mode sensor -User USER004       -> auto-detect COM port, collect
# The run itself opens in a new tab (-Here keeps it in the current terminal).
param(
    [ValidateSet('sensor', 'sim', '')][string]$Mode = '',
    [string]$Case = '',
    [string]$Users = '',
    [string]$User = '',
    [string]$Port = '',
    [double]$Speed = 1.0,
    [switch]$NoReset,
    [switch]$NoSave,
    [switch]$List,
    [switch]$Here   # run in this terminal instead of a new tab
)
. "$PSScriptRoot\_common.ps1"
Assert-Venv

function Ask($prompt, $default) {
    $a = Read-Host "$prompt [$default]"
    if ([string]::IsNullOrWhiteSpace($a)) { return $default }
    return $a.Trim()
}

function Invoke-Py {
    Push-Location $PyDir
    try { & $VenvPy @args } finally { Pop-Location }
}

# ---------- mode ----------
if (-not $Mode) {
    if ($List) { $Mode = 'sim' }
    else {
        Write-Host ''
        Write-Host '  1) Sensor      real Arduino over USB'
        Write-Host '  2) Simulation  fake data, 10 cases'
        $m = Ask 'Choose' '2'
        $Mode = if ($m -eq '1') { 'sensor' } else { 'sim' }
    }
}

if ($List) { Invoke-Py -m scripts.simulate_data --list; return }

if (-not (Test-Backend)) {
    throw "Backend not reachable at $ApiUrl. Run: start"
}

# ---------- sensor ----------
if ($Mode -eq 'sensor') {
    if (-not $Port) {
        Write-Step 'Detecting COM ports'
        $lines = Invoke-Py -m serial.tools.list_ports | Where-Object { $_ -match '^\s*(COM\d+)\s*(.*)$' }
        $ports = @()
        foreach ($l in $lines) {
            if ($l -match '^\s*(COM\d+)\s*(.*)$') { $ports += [pscustomobject]@{ Port = $Matches[1]; Desc = $Matches[2].Trim() } }
        }
        if ($ports.Count -eq 0) {
            throw 'No COM port found. Plug in the Arduino, close Serial Monitor, try again.'
        }
        $guess = $ports | Where-Object { $_.Desc -match 'Arduino|CH340|CH910|USB Serial|USB-SERIAL' } | Select-Object -First 1
        if ($ports.Count -eq 1) { $Port = $ports[0].Port }
        else {
            $i = 1
            foreach ($p in $ports) { Write-Host "  $i) $($p.Port)  $($p.Desc)"; $i++ }
            $def = if ($guess) { [string]([array]::IndexOf($ports, $guess) + 1) } else { '1' }
            $pick = [int](Ask 'Choose port' $def)
            $Port = $ports[$pick - 1].Port
        }
        Write-Ok "using $Port"
    }
    if (-not $User) { $User = Ask 'User ID' 'USER001' }

    # COM port can be held by one program only: Arduino IDE Serial Monitor, another collector, PuTTY.
    function Test-PortFree {
        Invoke-Py -c "import serial,sys; serial.Serial(sys.argv[1]).close()" $Port *> $null
        return ($LASTEXITCODE -eq 0)
    }
    if (-not (Test-PortFree)) {
        Write-Warn2 "$Port is busy (Access is denied). Looking for the program that holds it..."
        $stale = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
            Where-Object { $_.CommandLine -match 'serial_collector' }
        foreach ($p in $stale) { Write-Warn2 "old collector (PID $($p.ProcessId)) stopped"; Stop-Tree $p.ProcessId }
        $mon = Get-Process serial-monitor, putty, plink -ErrorAction SilentlyContinue
        if ($mon) {
            Write-Warn2 ("holding the port: " + (($mon | ForEach-Object { $_.ProcessName }) -join ', '))
            $yes = Ask 'Stop it now? (the Arduino IDE itself stays open)' 'y'
            if ($yes -match '^y') { $mon | ForEach-Object { Stop-Tree $_.Id } }
        }
        Start-Sleep -Seconds 1
        if (-not (Test-PortFree)) {
            throw "$Port still busy. Close Arduino IDE Serial Monitor (and Serial Plotter), unplug/replug the USB cable, run again."
        }
        Write-Ok "$Port is free now"
    }
    Write-Host ''
    Write-Host "Dashboard: pick user $User in the User dropdown (top right)." -ForegroundColor Yellow
    Write-Host 'Ctrl+C stops the collector. Serial Monitor must be closed.' -ForegroundColor Yellow
    Write-Host ''
    if (-not $Here) {
        $self = Join-Path $PSScriptRoot 'run-data.ps1'
        Start-Tab "Sensor $User" $PyDir "& '$self' -Mode sensor -User $User -Port $Port -Here" -KeepOpen
        Write-Ok 'sensor collector opened in a new tab'
        return
    }
    Invoke-Py -m collector.serial_collector --port $Port --user $User --api $ApiUrl
    return
}

# ---------- simulation ----------
if (-not $Case) {
    Invoke-Py -m scripts.simulate_data --list
    $Case = Ask 'Case number (1-10, or all)' '1'
}
if (-not $Users) { $Users = Ask 'Users (comma separated)' 'USER001,USER002' }

if (-not $Here) {
    $self = Join-Path $PSScriptRoot 'run-data.ps1'
    $extra = @("-Speed $Speed")
    if ($NoReset) { $extra += '-NoReset' }
    if ($NoSave)  { $extra += '-NoSave' }
    Start-Tab "Sim case $Case" $PyDir "& '$self' -Mode sim -Case $Case -Users '$Users' $($extra -join ' ') -Here" -KeepOpen
    Write-Ok "simulation case $Case opened in a new tab"
    Write-Host "Dashboard: pick one of [$Users] in the User dropdown." -ForegroundColor Yellow
    return
}

$cases = if ($Case -eq 'all') { 1..10 } else { @([int]$Case) }
foreach ($c in $cases) {
    $simArgs = @('-m', 'scripts.simulate_data', '--case', $c, '--users', $Users, '--speed', $Speed, '--api', $ApiUrl)
    if ($NoReset) { $simArgs += '--no-reset' }
    if ($NoSave)  { $simArgs += '--no-save' }
    Write-Step "Simulation case $c  (users: $Users)"
    Invoke-Py @simArgs
}
Write-Host ''
Write-Host "Dashboard: pick one of [$Users] in the User dropdown." -ForegroundColor Yellow
