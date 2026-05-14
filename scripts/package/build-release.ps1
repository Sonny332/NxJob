param(
  [string]$Version = "0.5.0",
  [switch]$SkipChecks,
  [switch]$SkipValidation
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$artifactsDir = Join-Path $root "releases\$Version"
New-Item -ItemType Directory -Force -Path $artifactsDir | Out-Null

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

Push-Location $root
try {
  $commit = (git rev-parse --short HEAD).Trim()
  if (-not $SkipChecks) {
    Invoke-Checked npm run shared:check
    Invoke-Checked npm run extension:typecheck
    $env:PYTHONDONTWRITEBYTECODE = "1"
    $pythonPaths = @((Join-Path $root "apps\local-service\src"))
    $candidateDepsPaths = @(
      (Join-Path $root ".python-deps"),
      (Join-Path (Split-Path (Split-Path $root -Parent) -Parent) "NxJob\.python-deps")
    )
    foreach ($depsPath in $candidateDepsPaths) {
      if (Test-Path -LiteralPath $depsPath) {
        $pythonPaths = @($depsPath) + $pythonPaths
        break
      }
    }
    $env:PYTHONPATH = ($pythonPaths -join [System.IO.Path]::PathSeparator)

    $testRuntimeDir = Join-Path $root (".nxjob\release-test\run-" + [System.Guid]::NewGuid().ToString("N"))
    $testTempDir = Join-Path $testRuntimeDir "temp"
    $testLocalAppDataDir = Join-Path $testRuntimeDir "localappdata"
    $testGeneratedResumeDir = Join-Path $testRuntimeDir "generated-resumes"
    New-Item -ItemType Directory -Force -Path $testTempDir | Out-Null
    New-Item -ItemType Directory -Force -Path $testLocalAppDataDir | Out-Null
    New-Item -ItemType Directory -Force -Path $testGeneratedResumeDir | Out-Null
    $env:TEMP = $testTempDir
    $env:TMP = $testTempDir
    $env:LOCALAPPDATA = $testLocalAppDataDir
    $env:NXJOB_DB_PATH = Join-Path $testRuntimeDir "nxjob-test.sqlite3"
    $env:NXJOB_GENERATED_RESUME_DIR = $testGeneratedResumeDir

    Invoke-Checked -FilePath python -Arguments @(
      "-m",
      "pytest",
      "apps\local-service\tests",
      "-q",
      "--basetemp",
      $testTempDir,
      "-p",
      "no:cacheprovider"
    )
  }

  & (Join-Path $root "scripts\package\build-local-service.ps1") -Version $Version -ArtifactsDir $artifactsDir
  & (Join-Path $root "scripts\package\build-extension.ps1") -Version $Version -ArtifactsDir $artifactsDir

  $recordPath = Join-Path $artifactsDir "release-test-record-$Version.md"
  $manifestPath = Join-Path $artifactsDir "release-manifest.json"
  $bundleStage = Join-Path $artifactsDir "NxJob-$Version"
  $bundleZip = Join-Path $artifactsDir "NxJob-$Version.zip"
  $checksText = if ($SkipChecks) { "Skipped by -SkipChecks" } else { "Passed through build-release.ps1" }
  @"
# Release Test Record

## Version

- Version: $Version
- Commit: $commit
- Date: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")
- Tester:

## Artifacts

- One-click Windows package: NxJob-$Version.zip
- Local service package: nxjob-local-service-$Version.zip
- Browser extension package: nxjob-extension-$Version.zip
- Release manifest: release-manifest.json

## Automated Checks

- npm run shared:check: $checksText
- npm run extension:typecheck: $checksText
- python -m pytest apps/local-service/tests -q: $checksText
- scripts/package/build-release.ps1: Passed
- scripts/package/validate-release.ps1: Pending
- root .bat launchers: Generated

## Manual Smoke Test

- Local service install script completed:
- Install NxJob Local Service.bat completes:
- Start NxJob Local Service.bat starts the service:
- Check NxJob Local Service.bat returns ok:
- Status NxJob Local Service.bat reports healthy:
- Browser extension loads:
- Analyze Sponsorship button works:
- Tailor Resume button creates a DOCX:
- Fill Form Answer drafts and fills only after confirmation:
- Outcome entry creates SuccessReference:
- Stop NxJob Local Service.bat stops the service:
- Uninstall NxJob Local Service.bat removes service files:

## Data Boundary

- Real master resume is local only:
- private/ not included in Git diff:
- Generated resumes not included in Git diff:
- SQLite database not included in Git diff:
- Release zips do not contain private data:

## Version Differences

- Added:
- Changed:
- Fixed:
- Known limits:
"@ | Set-Content -LiteralPath $recordPath -Encoding UTF8

  $manifest = [ordered]@{
    version = $Version
    commit = $commit
    created_at = (Get-Date).ToString("o")
    artifacts = @(
      "NxJob-$Version.zip",
      "nxjob-local-service-$Version.zip",
      "nxjob-extension-$Version.zip",
      "release-manifest.json",
      "release-test-record-$Version.md"
    )
    checks = if ($SkipChecks) { "skipped" } else { "shared:check, extension:typecheck, pytest" }
    notes = "Windows-first MVP package. Private data is excluded."
  }
  $manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

  if (Test-Path -LiteralPath $bundleStage) {
    Remove-Item -LiteralPath $bundleStage -Recurse -Force
  }
  if (Test-Path -LiteralPath $bundleZip) {
    Remove-Item -LiteralPath $bundleZip -Force
  }
  Expand-Archive -LiteralPath (Join-Path $artifactsDir "nxjob-local-service-$Version.zip") -DestinationPath $bundleStage -Force
  Copy-Item -LiteralPath (Join-Path $artifactsDir "nxjob-extension-$Version.zip") -Destination (Join-Path $bundleStage "nxjob-extension-$Version.zip") -Force
  Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $bundleStage "release-manifest.json") -Force
  Copy-Item -LiteralPath $recordPath -Destination (Join-Path $bundleStage "release-test-record-$Version.md") -Force
  Compress-Archive -Path (Join-Path $bundleStage "*") -DestinationPath $bundleZip -Force

  if (-not $SkipValidation) {
    & (Join-Path $root "scripts\package\validate-release.ps1") -Version $Version -ArtifactsDir $artifactsDir
    (Get-Content -LiteralPath $recordPath -Raw).Replace("scripts/package/validate-release.ps1: Pending", "scripts/package/validate-release.ps1: Passed") | Set-Content -LiteralPath $recordPath -Encoding UTF8
    Copy-Item -LiteralPath $recordPath -Destination (Join-Path $bundleStage "release-test-record-$Version.md") -Force
    Compress-Archive -Path (Join-Path $bundleStage "*") -DestinationPath $bundleZip -Force
  }
  Write-Host "Release artifacts written to $artifactsDir"
}
finally {
  Pop-Location
}
