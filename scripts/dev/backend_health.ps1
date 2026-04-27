$ErrorActionPreference = 'Stop'

$port = 8000
$healthUrl = "http://127.0.0.1:$port/v1/health"
$response = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 10

Write-Output "Status: $($response.StatusCode)"
Write-Output $response.Content
