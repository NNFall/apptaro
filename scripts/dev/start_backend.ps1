$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$backendDir = Join-Path $repoRoot 'backend'
$pythonExe = Join-Path $backendDir '.venv\Scripts\python.exe'
$stdoutLog = Join-Path $backendDir 'runtime\temp\uvicorn.stdout.log'
$stderrLog = Join-Path $backendDir 'runtime\temp\uvicorn.stderr.log'
$port = 8000
$healthUrl = "http://127.0.0.1:$port/v1/health"

if (-not (Test-Path $pythonExe)) {
  throw "Backend venv not found: $pythonExe"
}

$existingListeners = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
  Where-Object { $_.State -eq 'Listen' }

if ($existingListeners) {
  $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($existingListeners[0].OwningProcess)"
  $commandLine = [string]$process.CommandLine
  $matchesBackend =
    $commandLine.IndexOf($pythonExe, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
    $commandLine.IndexOf('uvicorn', [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
    $commandLine.IndexOf('src.main:app', [System.StringComparison]::OrdinalIgnoreCase) -ge 0
  if ($matchesBackend) {
    Write-Output "Backend already running on $healthUrl (PID $($process.ProcessId))."
    exit 0
  }
  throw "Port $port is already in use by another process (PID $($process.ProcessId))."
}

New-Item -ItemType Directory -Path (Split-Path -Parent $stdoutLog) -Force | Out-Null
if (Test-Path $stdoutLog) { Remove-Item -LiteralPath $stdoutLog -Force }
if (Test-Path $stderrLog) { Remove-Item -LiteralPath $stderrLog -Force }

$process = Start-Process `
  -FilePath $pythonExe `
  -ArgumentList '-m','uvicorn','src.main:app','--host','127.0.0.1','--port',"$port" `
  -WorkingDirectory $backendDir `
  -WindowStyle Hidden `
  -RedirectStandardOutput $stdoutLog `
  -RedirectStandardError $stderrLog `
  -PassThru

Start-Sleep -Seconds 3

$health = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 10

Write-Output "Backend started. PID: $($process.Id)"
Write-Output "Health: $($health.StatusCode) $($health.Content)"
Write-Output "Stdout: $stdoutLog"
Write-Output "Stderr: $stderrLog"
