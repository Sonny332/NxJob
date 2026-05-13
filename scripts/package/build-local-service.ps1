param(
  [string]$Version = "0.4.0",
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
$scriptSourceDir = Join-Path $root "scripts\package\local-service-scripts"
$rootScriptSourceDir = Join-Path $root "scripts\package\local-service-root-scripts"

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
Get-ChildItem -LiteralPath (Join-Path $stage "app\local-service\src") -Directory -Recurse -Force |
  Where-Object { $_.Name -eq "__pycache__" } |
  Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath (Join-Path $stage "app\local-service\src") -File -Recurse -Force |
  Where-Object { $_.Extension -in @(".pyc", ".pyo") } |
  Remove-Item -Force
Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination (Join-Path $stage "README.md") -Force
Copy-Item -LiteralPath (Join-Path $root "LICENSE") -Destination (Join-Path $stage "LICENSE") -Force
Copy-Item -LiteralPath (Join-Path $root "docs\install-windows.md") -Destination (Join-Path $stage "docs\install-windows.md") -Force
Copy-Item -LiteralPath (Join-Path $root "docs\master-resume-format.md") -Destination (Join-Path $stage "docs\master-resume-format.md") -Force
Copy-Item -LiteralPath (Join-Path $root "docs\privacy-boundary.md") -Destination (Join-Path $stage "docs\privacy-boundary.md") -Force
Copy-Item -Path (Join-Path $scriptSourceDir "*") -Destination (Join-Path $stage "scripts") -Force
Copy-Item -Path (Join-Path $rootScriptSourceDir "*.bat") -Destination $stage -Force
Set-Content -LiteralPath (Join-Path $stage "VERSION") -Value $Version -Encoding UTF8

if (Test-Path -LiteralPath $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -Force
Write-Host "Local service package: $zipPath"
