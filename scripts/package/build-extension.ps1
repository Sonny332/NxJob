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
$extensionDir = Join-Path $root "apps\extension"
$outputDir = Join-Path (Join-Path ([System.IO.Path]::GetTempPath()) "NxJobReleaseWxt") "nxjob-extension-$Version-$([System.Guid]::NewGuid().ToString('N'))"
$builtOutputDir = Join-Path $outputDir "chrome-mv3"
$artifactName = "nxjob-extension-$Version.zip"
$artifactPath = Join-Path $ArtifactsDir $artifactName

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

function Get-ChromeExtensionVersion {
  param([Parameter(Mandatory = $true)][string]$ReleaseVersion)
  if ($ReleaseVersion -match "^(?<numeric>\d+\.\d+\.\d+(?:\.\d+)?)") {
    return $Matches.numeric
  }
  throw "Release version '$ReleaseVersion' does not start with a Chrome extension compatible numeric version."
}

New-Item -ItemType Directory -Force -Path $ArtifactsDir | Out-Null
Push-Location $root
try {
  $previousWxtOutDir = $env:NXJOB_WXT_OUT_DIR
  $previousBuiltManifest = $env:NXJOB_WXT_BUILT_MANIFEST
  $previousExtensionVersion = $env:NXJOB_EXTENSION_VERSION
  $previousReleaseVersion = $env:NXJOB_RELEASE_VERSION
  $env:NXJOB_WXT_OUT_DIR = $outputDir
  $env:NXJOB_WXT_BUILT_MANIFEST = Join-Path $builtOutputDir "manifest.json"
  $env:NXJOB_EXTENSION_VERSION = Get-ChromeExtensionVersion -ReleaseVersion $Version
  $env:NXJOB_RELEASE_VERSION = $Version
  Invoke-Checked npm run extension:build
  Invoke-Checked node (Join-Path $root "scripts\package\validate-extension-manifest.mjs") --check-built --version $Version
  Invoke-Checked npm --workspace "@nxjob/extension" run zip
}
finally {
  $env:NXJOB_WXT_OUT_DIR = $previousWxtOutDir
  $env:NXJOB_WXT_BUILT_MANIFEST = $previousBuiltManifest
  $env:NXJOB_EXTENSION_VERSION = $previousExtensionVersion
  $env:NXJOB_RELEASE_VERSION = $previousReleaseVersion
  Pop-Location
}

$zip = Get-ChildItem -Path $outputDir -Filter "*.zip" -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $zip) {
  throw "WXT zip artifact was not generated under $outputDir."
}

Copy-Item -LiteralPath $zip.FullName -Destination $artifactPath -Force
try {
  Remove-Item -LiteralPath $outputDir -Recurse -Force
}
catch {
  Write-Warning "Could not remove extension build output directory '$outputDir'. $($_.Exception.Message)"
}
Write-Host "Extension package: $artifactPath"
