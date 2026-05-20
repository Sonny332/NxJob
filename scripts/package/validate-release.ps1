param(
  [string]$Version = "0.6.0",
  [string]$ArtifactsDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not $ArtifactsDir) {
  $ArtifactsDir = Join-Path $root "releases\$Version"
}
$ArtifactsDir = [System.IO.Path]::GetFullPath($ArtifactsDir)

function Assert-Exists {
  param([Parameter(Mandatory = $true)][string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    throw "Missing required release artifact: $Path"
  }
}

function Get-ZipEntries {
  param([Parameter(Mandatory = $true)][string]$ZipPath)
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
  try {
    return @($archive.Entries | ForEach-Object { $_.FullName.Replace("\", "/") })
  }
  finally {
    $archive.Dispose()
  }
}

function Assert-ZipContains {
  param(
    [string[]]$Entries,
    [string[]]$Required
  )
  foreach ($requiredEntry in $Required) {
    if (-not ($Entries -contains $requiredEntry)) {
      throw "Zip is missing required entry: $requiredEntry"
    }
  }
}

function Assert-ZipExcludes {
  param(
    [string[]]$Entries,
    [string[]]$ForbiddenPatterns
  )
  foreach ($entry in $Entries) {
    foreach ($pattern in $ForbiddenPatterns) {
      if ($entry -like $pattern) {
        throw "Zip contains forbidden entry '$entry' matching '$pattern'"
      }
    }
  }
}

$localServiceZip = Join-Path $ArtifactsDir "nxjob-local-service-$Version.zip"
$extensionZip = Join-Path $ArtifactsDir "nxjob-extension-$Version.zip"
$bundleZip = Join-Path $ArtifactsDir "NxJob-$Version.zip"
$manifestPath = Join-Path $ArtifactsDir "release-manifest.json"
$recordPath = Join-Path $ArtifactsDir "release-test-record-$Version.md"

Assert-Exists -Path $localServiceZip
Assert-Exists -Path $extensionZip
Assert-Exists -Path $bundleZip
Assert-Exists -Path $manifestPath
Assert-Exists -Path $recordPath

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.version -ne $Version) {
  throw "Manifest version '$($manifest.version)' does not match expected '$Version'."
}

$localEntries = Get-ZipEntries -ZipPath $localServiceZip
Assert-ZipContains -Entries $localEntries -Required @(
  "README.md",
  "LICENSE",
  "VERSION",
  "Install NxJob Local Service.bat",
  "Start NxJob Local Service.bat",
  "Check NxJob Local Service.bat",
  "Status NxJob Local Service.bat",
  "Stop NxJob Local Service.bat",
  "Uninstall NxJob Local Service.bat",
  "app/local-service/pyproject.toml",
  "scripts/install-local-service.ps1",
  "scripts/install-local-service.bat",
  "scripts/start-local-service.ps1",
  "scripts/start-local-service.bat",
  "scripts/status-local-service.ps1",
  "scripts/status-local-service.bat",
  "scripts/stop-local-service.ps1",
  "scripts/stop-local-service.bat",
  "scripts/uninstall-local-service.ps1",
  "scripts/uninstall-local-service.bat",
  "scripts/check-health.ps1",
  "scripts/check-health.bat",
  "docs/install-windows.md",
  "docs/master-resume-format.md",
  "docs/privacy-boundary.md"
)
Assert-ZipExcludes -Entries $localEntries -ForbiddenPatterns @(
  "private/*",
  "*/private/*",
  "*.db",
  "*.sqlite",
  "*.sqlite3",
  ".venv/*",
  "*/.venv/*",
  ".pytest_cache/*",
  "*/.pytest_cache/*",
  "__pycache__/*",
  "*/__pycache__/*"
)

$extensionEntries = Get-ZipEntries -ZipPath $extensionZip
Assert-ZipContains -Entries $extensionEntries -Required @(
  "manifest.json",
  "popup.html",
  "background.js",
  "assets/icons/nxjob-16.png",
  "assets/icons/nxjob-32.png",
  "assets/icons/nxjob-48.png",
  "assets/icons/nxjob-128.png"
)
Assert-ZipExcludes -Entries $extensionEntries -ForbiddenPatterns @(
  "private/*",
  "*/private/*",
  "node_modules/*",
  "*/node_modules/*",
  "*.map"
)

$bundleEntries = Get-ZipEntries -ZipPath $bundleZip
Assert-ZipContains -Entries $bundleEntries -Required @(
  "Install NxJob Local Service.bat",
  "Start NxJob Local Service.bat",
  "Check NxJob Local Service.bat",
  "Status NxJob Local Service.bat",
  "Stop NxJob Local Service.bat",
  "Uninstall NxJob Local Service.bat",
  "scripts/install-local-service.ps1",
  "scripts/install-local-service.bat",
  "docs/install-windows.md",
  "release-manifest.json",
  "release-test-record-$Version.md",
  "nxjob-extension-$Version.zip"
)
Assert-ZipExcludes -Entries $bundleEntries -ForbiddenPatterns @(
  "scripts/package/*",
  "*/scripts/package/*",
  "private/*",
  "*/private/*",
  "*.db",
  "*.sqlite",
  "*.sqlite3",
  ".venv/*",
  "*/.venv/*",
  ".pytest_cache/*",
  "*/.pytest_cache/*",
  "__pycache__/*",
  "*/__pycache__/*"
)

Write-Host "Release validation passed for $Version"
