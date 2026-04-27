$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$backendDir = Join-Path $repoRoot 'backend'
$pythonExe = Join-Path $backendDir '.venv\Scripts\python.exe'
$port = 8000

$listeners = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
  Where-Object { $_.State -eq 'Listen' }

if (-not $listeners) {
  Write-Output "Backend is not running on port $port."
  exit 0
}

$process = Get-CimInstance Win32_Process -Filter "ProcessId = $($listeners[0].OwningProcess)"
$commandLine = [string]$process.CommandLine
$matchesBackend =
  $commandLine.IndexOf($pythonExe, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
  $commandLine.IndexOf('uvicorn', [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
  $commandLine.IndexOf('src.main:app', [System.StringComparison]::OrdinalIgnoreCase) -ge 0

if (-not $matchesBackend) {
  throw "Process on port $port is not the AppSlides backend (PID $($process.ProcessId))."
}

Stop-Process -Id $process.ProcessId -Force
Write-Output "Backend stopped. PID: $($process.ProcessId)"
