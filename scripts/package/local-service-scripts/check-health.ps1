param(
  [string]$HostAddress = "127.0.0.1",
  [int]$Port = 8765,
  [int]$TimeoutSec = 5
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$uri = "http://${HostAddress}:${Port}/health"
try {
  $response = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec $TimeoutSec
  $response | ConvertTo-Json
}
catch {
  Write-Error "NxJob Local Service is not reachable at $uri"
}
