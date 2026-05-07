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

function Get-PortOwnerSummary {
  param(
    [string]$Address,
    [int]$Port
  )
  try {
    $connection = Get-NetTCPConnection -LocalAddress $Address -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($connection) {
      $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
      $name = if ($process) { $process.ProcessName } else { "unknown" }
      return "PID $($connection.OwningProcess) ($name)"
    }
  }
  catch {
    return ""
  }
  return ""
}

function Get-LogTail {
  param([string]$Path)
  if (Test-Path -LiteralPath $Path) {
    return (Get-Content -LiteralPath $Path -Tail 40 -ErrorAction SilentlyContinue) -join [Environment]::NewLine
  }
  return ""
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
$serviceSrc = Join-Path $InstallRoot "app\local-service\src"
if (-not (Test-Path -LiteralPath $serviceSrc)) {
  throw "NxJob Local Service source is missing at $serviceSrc. Run scripts\install-local-service.ps1 again."
}

$healthUri = "http://${HostAddress}:${Port}/health"
if (Test-Health -Uri $healthUri) {
  Write-Host "NxJob Local Service is already healthy at $healthUri"
  return
}

$owner = Get-PortOwnerSummary -Address $HostAddress -Port $Port
if ($owner) {
  throw "Port ${HostAddress}:${Port} is already in use by $owner, but it is not responding as NxJob. Stop that process or start NxJob on a different port."
}

$arguments = @(
  "-m", "uvicorn", "nxjob.main:app",
  "--app-dir", $serviceSrc,
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
  try {
    Wait-ForHealth -Uri $healthUri
  }
  catch {
    $current = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
    if (-not $current) {
      Remove-Item -LiteralPath (Join-Path $InstallRoot "nxjob-local-service.pid") -Force -ErrorAction SilentlyContinue
      $errorTail = Get-LogTail -Path $stderr
      if ($errorTail) {
        throw "NxJob Local Service exited before becoming healthy at $healthUri.$([Environment]::NewLine)$errorTail"
      }
      throw "NxJob Local Service exited before becoming healthy at $healthUri. No stderr log was written."
    }
    $errorTail = Get-LogTail -Path $stderr
    if ($errorTail) {
      throw "NxJob Local Service process $($process.Id) is still running but did not become healthy at $healthUri.$([Environment]::NewLine)$errorTail"
    }
    throw
  }
  Write-Host "NxJob Local Service started in background at $healthUri"
  Write-Host "PID: $($process.Id)"
  return
}

& $python @arguments
