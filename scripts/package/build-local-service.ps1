param(
  [string]$Version = "0.1.0",
  [string]$ArtifactsDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not $ArtifactsDir) {
  $ArtifactsDir = Join-Path $root "releases\$Version"
}
$ArtifactsDir = [System.IO.Path]::GetFullPath($ArtifactsDir)
$stage = Join-Path $ArtifactsDir "nxjob-local-service-$Version"
$zipPath = Join-Path $ArtifactsDir "nxjob-local-service-$Version.zip"

if (Test-Path -LiteralPath $stage) {
  Remove-Item -LiteralPath $stage -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $stage | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "app") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "app\local-service") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "scripts") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "docs") | Out-Null

Copy-Item -LiteralPath (Join-Path $root "apps\local-service\pyproject.toml") -Destination (Join-Path $stage "app\local-service\pyproject.toml") -Force
Copy-Item -Path (Join-Path $root "apps\local-service\src") -Destination (Join-Path $stage "app\local-service\src") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination (Join-Path $stage "README.md") -Force
Copy-Item -LiteralPath (Join-Path $root "LICENSE") -Destination (Join-Path $stage "LICENSE") -Force
Copy-Item -LiteralPath (Join-Path $root "docs\install-windows.md") -Destination (Join-Path $stage "docs\install-windows.md") -Force
Copy-Item -LiteralPath (Join-Path $root "docs\master-resume-format.md") -Destination (Join-Path $stage "docs\master-resume-format.md") -Force
Copy-Item -LiteralPath (Join-Path $root "docs\privacy-boundary.md") -Destination (Join-Path $stage "docs\privacy-boundary.md") -Force

@'
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Checked {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
  )
  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
  }
}

$installRoot = Join-Path $env:LOCALAPPDATA "NxJob\LocalService"
$sourceRoot = Join-Path $PSScriptRoot "..\app\local-service"
$venv = Join-Path $installRoot ".venv"

New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
Copy-Item -Path (Join-Path $sourceRoot "*") -Destination $installRoot -Recurse -Force

Push-Location $installRoot
try {
  if (-not (Test-Path -LiteralPath $venv)) {
    Invoke-Checked python -m venv $venv
  }
  Invoke-Checked (Join-Path $venv "Scripts\python.exe") -m pip install --upgrade pip
  Invoke-Checked (Join-Path $venv "Scripts\python.exe") -m pip install .
}
finally {
  Pop-Location
}

Write-Host "NxJob Local Service installed at $installRoot"
Write-Host "Start it with scripts\start-local-service.ps1"
'@ | Set-Content -LiteralPath (Join-Path $stage "scripts\install-local-service.ps1") -Encoding UTF8

@'
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$installRoot = Join-Path $env:LOCALAPPDATA "NxJob\LocalService"
$python = Join-Path $installRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
  throw "NxJob Local Service is not installed. Run scripts\install-local-service.ps1 first."
}

& $python -m uvicorn nxjob.main:app --app-dir (Join-Path $installRoot "src") --host 127.0.0.1 --port 8765
'@ | Set-Content -LiteralPath (Join-Path $stage "scripts\start-local-service.ps1") -Encoding UTF8

@'
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

try {
  $response = Invoke-RestMethod -Uri "http://127.0.0.1:8765/health" -Method Get -TimeoutSec 5
  $response | ConvertTo-Json
}
catch {
  Write-Error "NxJob Local Service is not reachable at http://127.0.0.1:8765/health"
}
'@ | Set-Content -LiteralPath (Join-Path $stage "scripts\check-health.ps1") -Encoding UTF8

if (Test-Path -LiteralPath $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -Force
Write-Host "Local service package: $zipPath"
