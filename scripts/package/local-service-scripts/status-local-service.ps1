param(
  [string]$InstallRoot = "",
  [string]$HostAddress = "127.0.0.1",
  [int]$Port = 8765
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $InstallRoot) {
  if (-not $env:LOCALAPPDATA) {
    throw "LOCALAPPDATA is not set. Pass -InstallRoot explicitly."
  }
  $InstallRoot = Join-Path $env:LOCALAPPDATA "NxJob\LocalService"
}

$pidFile = Join-Path $InstallRoot "nxjob-local-service.pid"
$pidValue = $null
$processRunning = $false
if (Test-Path -LiteralPath $pidFile) {
  $pidValue = (Get-Content -LiteralPath $pidFile -TotalCount 1).Trim()
  if ($pidValue) {
    $processRunning = $null -ne (Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue)
  }
}

$healthUri = "http://${HostAddress}:${Port}/health"
$healthy = $false
try {
  Invoke-RestMethod -Uri $healthUri -Method Get -TimeoutSec 2 | Out-Null
  $healthy = $true
}
catch {
  $healthy = $false
}

[ordered]@{
  install_root = $InstallRoot
  pid = $pidValue
  process_running = $processRunning
  health_uri = $healthUri
  healthy = $healthy
} | ConvertTo-Json -Depth 4
