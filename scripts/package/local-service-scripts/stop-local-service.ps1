param(
  [string]$InstallRoot = ""
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
if (-not (Test-Path -LiteralPath $pidFile)) {
  Write-Host "No NxJob Local Service PID file found."
  return
}

$pidValue = (Get-Content -LiteralPath $pidFile -TotalCount 1).Trim()
if (-not $pidValue) {
  Remove-Item -LiteralPath $pidFile -Force
  Write-Host "Empty PID file removed."
  return
}

$process = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
if ($process) {
  $expectedPython = Join-Path $InstallRoot ".venv\Scripts\python.exe"
  if ($process.Path -and (Test-Path -LiteralPath $expectedPython)) {
    $actualPath = (Resolve-Path -LiteralPath $process.Path).Path
    $expectedPath = (Resolve-Path -LiteralPath $expectedPython).Path
    if ($actualPath -ne $expectedPath) {
      throw "PID $pidValue is not the NxJob venv Python process. Refusing to stop it."
    }
  }
  Stop-Process -Id $process.Id -Force
  Write-Host "Stopped NxJob Local Service process $($process.Id)."
}
else {
  Write-Host "NxJob Local Service process $pidValue is not running."
}

Remove-Item -LiteralPath $pidFile -Force
