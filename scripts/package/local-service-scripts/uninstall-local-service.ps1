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

$stopScript = Join-Path $PSScriptRoot "stop-local-service.ps1"
if (Test-Path -LiteralPath $stopScript) {
  & $stopScript -InstallRoot $InstallRoot
}

if (Test-Path -LiteralPath $InstallRoot) {
  Remove-Item -LiteralPath $InstallRoot -Recurse -Force
  Write-Host "Removed NxJob Local Service from $InstallRoot"
}
else {
  Write-Host "NxJob Local Service is not installed at $InstallRoot"
}

Write-Host "Local NxJob data outside LocalService was not removed."
