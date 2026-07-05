param(
  [string]$Version = "0.6.2",
  [string]$ArtifactsDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not $ArtifactsDir) {
  $ArtifactsDir = Join-Path $root "releases\$Version"
}
$ArtifactsDir = [System.IO.Path]::GetFullPath($ArtifactsDir)
. (Join-Path $PSScriptRoot "release-version.ps1")

function Assert-Exists {
  param([Parameter(Mandatory = $true)][string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    throw "Missing required release artifact: $Path"
  }
}

function Use-ZipArchive {
  param(
    [Parameter(Mandatory = $true)][string]$ZipPath,
    [Parameter(Mandatory = $true)][scriptblock]$Action
  )
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
  try {
    return & $Action $archive
  }
  finally {
    $archive.Dispose()
  }
}

function Get-ZipEntries {
  param([Parameter(Mandatory = $true)][string]$ZipPath)
  return @(Use-ZipArchive -ZipPath $ZipPath -Action { param($archive) $archive.Entries | ForEach-Object { $_.FullName.Replace("\", "/") } })
}

function Get-ZipEntryText {
  param(
    [Parameter(Mandatory = $true)][string]$ZipPath,
    [Parameter(Mandatory = $true)][string]$EntryName
  )
  return Use-ZipArchive -ZipPath $ZipPath -Action {
    param($archive)
    $normalizedEntryName = $EntryName.Replace("\", "/")
    $entry = $archive.Entries | Where-Object { $_.FullName.Replace("\", "/") -eq $normalizedEntryName } | Select-Object -First 1
    if ($null -eq $entry) {
      throw "Zip is missing required entry: $EntryName"
    }
    $stream = $entry.Open()
    try {
      $reader = [System.IO.StreamReader]::new($stream)
      try {
        return $reader.ReadToEnd()
      }
      finally {
        $reader.Dispose()
      }
    }
    finally {
      $stream.Dispose()
    }
  }
}

function Get-ZipEntryBytes {
  param(
    [Parameter(Mandatory = $true)][string]$ZipPath,
    [Parameter(Mandatory = $true)][string]$EntryName
  )
  return Use-ZipArchive -ZipPath $ZipPath -Action {
    param($archive)
    $normalizedEntryName = $EntryName.Replace("\", "/")
    $entry = $archive.Entries | Where-Object { $_.FullName.Replace("\", "/") -eq $normalizedEntryName } | Select-Object -First 1
    if ($null -eq $entry) {
      throw "Zip is missing required entry: $EntryName"
    }
    $stream = $entry.Open()
    try {
      $memory = [System.IO.MemoryStream]::new()
      try {
        $stream.CopyTo($memory)
        return $memory.ToArray()
      }
      finally {
        $memory.Dispose()
      }
    }
    finally {
      $stream.Dispose()
    }
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

function Assert-LocalServiceVersion {
  param(
    [Parameter(Mandatory = $true)][string]$ZipPath,
    [Parameter(Mandatory = $true)][string]$ReleaseVersion
  )

  $expectedPackageVersion = Convert-ReleaseVersionToPythonPackageVersion -ReleaseVersion $ReleaseVersion
  $versionText = (Get-ZipEntryText -ZipPath $ZipPath -EntryName "VERSION").Trim()
  if ($versionText -ne $ReleaseVersion) {
    throw "Local service VERSION '$versionText' does not match release version '$ReleaseVersion'."
  }

  $pyproject = Get-ZipEntryText -ZipPath $ZipPath -EntryName "app/local-service/pyproject.toml"
  $pyprojectBytes = Get-ZipEntryBytes -ZipPath $ZipPath -EntryName "app/local-service/pyproject.toml"
  if ($pyprojectBytes.Length -ge 3 -and $pyprojectBytes[0] -eq 0xEF -and $pyprojectBytes[1] -eq 0xBB -and $pyprojectBytes[2] -eq 0xBF) {
    throw "Local service pyproject.toml must be UTF-8 without BOM; pip/tomllib rejects BOM-prefixed TOML."
  }
  if ($pyproject -notmatch '(?m)^version\s*=\s*"([^"]+)"') {
    throw "Local service pyproject.toml is missing project version."
  }
  if ($Matches[1] -ne $expectedPackageVersion) {
    throw "Local service pyproject.toml version '$($Matches[1])' does not match expected package version '$expectedPackageVersion'."
  }

  $init = Get-ZipEntryText -ZipPath $ZipPath -EntryName "app/local-service/src/nxjob/__init__.py"
  if ($init -notmatch '(?m)^__version__\s*=\s*"([^"]+)"') {
    throw "Local service nxjob.__version__ is missing."
  }
  if ($Matches[1] -ne $expectedPackageVersion) {
    throw "Local service nxjob.__version__ '$($Matches[1])' does not match expected package version '$expectedPackageVersion'."
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
Assert-LocalServiceVersion -ZipPath $localServiceZip -ReleaseVersion $Version

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
$extensionManifest = Get-ZipEntryText -ZipPath $extensionZip -EntryName "manifest.json" | ConvertFrom-Json
if ($Version -match "^(?<numeric>\d+\.\d+\.\d+(?:\.\d+)?)") {
  if ($extensionManifest.version -ne $Matches.numeric) {
    throw "Extension manifest version '$($extensionManifest.version)' does not match expected Chrome version '$($Matches.numeric)'."
  }
}
else {
  throw "Release version '$Version' does not start with a Chrome extension compatible numeric version."
}
$extensionManifestVersionName = if ($extensionManifest.PSObject.Properties.Name -contains "version_name") {
  $extensionManifest.version_name
}
else {
  ""
}
if ($extensionManifestVersionName -ne $Version -and ($Version -ne $extensionManifest.version -or $extensionManifestVersionName)) {
  throw "Extension manifest version_name '$extensionManifestVersionName' does not match release version '$Version'."
}

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
Assert-LocalServiceVersion -ZipPath $bundleZip -ReleaseVersion $Version

Write-Host "Release validation passed for $Version"
