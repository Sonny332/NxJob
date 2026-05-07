param(
  [string]$InstallRoot = "",
  [string]$HostAddress = "127.0.0.1",
  [int]$Port = 8765,
  [switch]$Background
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-Health {
  param([string]$Uri)
  try {
    Invoke-RestMethod -Uri $Uri -Method Get -TimeoutSec 2 | Out-Null
    return $true
  }
  catch {
    return $false
  }
}

function Wait-ForHealth {
  param([string]$Uri)
  for ($i = 0; $i -lt 20; $i++) {
    if (Test-Health -Uri $Uri) {
      return
    }
    Start-Sleep -Milliseconds 500
  }
  throw "NxJob Local Service did not become healthy at $Uri."
}

if (-not $InstallRoot) {
  if (-not $env:LOCALAPPDATA) {
    throw "LOCALAPPDATA is not set. Pass -InstallRoot explicitly."
  }
  $InstallRoot = Join-Path $env:LOCALAPPDATA "NxJob\LocalService"
}

$python = Join-Path $InstallRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
  throw "NxJob Local Service is not installed. Run scripts\install-local-service.ps1 first."
}

$healthUri = "http://${HostAddress}:${Port}/health"
if (Test-Health -Uri $healthUri) {
  Write-Host "NxJob Local Service is already healthy at $healthUri"
  return
}

$arguments = @(
  "-m", "uvicorn", "nxjob.main:app",
  "--app-dir", (Join-Path $InstallRoot "src"),
  "--host", $HostAddress,
  "--port", "$Port"
)

if ($Background) {
  $logDir = Join-Path $InstallRoot "logs"
  New-Item -ItemType Directory -Force -Path $logDir | Out-Null
  $stdout = Join-Path $logDir "service.out.log"
  $stderr = Join-Path $logDir "service.err.log"
  $process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $InstallRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  Set-Content -LiteralPath (Join-Path $InstallRoot "nxjob-local-service.pid") -Value $process.Id -Encoding UTF8
  Wait-ForHealth -Uri $healthUri
  Write-Host "NxJob Local Service started in background at $healthUri"
  Write-Host "PID: $($process.Id)"
  return
}

& $python @arguments
