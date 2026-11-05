# Close the backend and frontend windows started by start-all. Docker and its data volume stay.
. "$PSScriptRoot\_common.ps1"

# Each tab's shell wrote its PID. Kill only the shell's children (uvicorn / npm trees):
# the shell then exits 0 and Windows Terminal closes the tab by itself.
if (Test-Path $PidDir) {
    foreach ($f in Get-ChildItem $PidDir -File) {
        $shellPid = [int](Get-Content $f.FullName -ErrorAction SilentlyContinue)
        $shell = Get-Process -Id $shellPid -ErrorAction SilentlyContinue
        if ($shell -and $shell.ProcessName -like 'powershell*') {
            Get-CimInstance Win32_Process -Filter "ParentProcessId=$shellPid" |
                ForEach-Object { Stop-Tree $_.ProcessId }
        }
    }
    Remove-Item $PidDir -Recurse -Force
}
# Catch orphans (windows closed by hand, reload children).
Stop-Port 8000
Stop-Port 5173
Write-Ok 'backend + frontend windows closed'
