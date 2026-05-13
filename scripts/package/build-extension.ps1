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
$extensionDir = Join-Path $root "apps\extension"
$outputDir = Join-Path $extensionDir ".output"
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

New-Item -ItemType Directory -Force -Path $ArtifactsDir | Out-Null
Push-Location $root
try {
  Invoke-Checked npm run extension:build
  Invoke-Checked npm --workspace "@nxjob/extension" run zip
}
finally {
  Pop-Location
}

$zip = Get-ChildItem -Path $outputDir -Filter "*.zip" -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $zip) {
  throw "WXT zip artifact was not generated under $outputDir."
}

Copy-Item -LiteralPath $zip.FullName -Destination $artifactPath -Force
Write-Host "Extension package: $artifactPath"
