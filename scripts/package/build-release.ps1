param(
  [string]$Version = "0.1.0",
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
    Invoke-Checked python -m pytest apps\local-service\tests -q
  }

  & (Join-Path $root "scripts\package\build-local-service.ps1") -Version $Version -ArtifactsDir $artifactsDir
  & (Join-Path $root "scripts\package\build-extension.ps1") -Version $Version -ArtifactsDir $artifactsDir

  $recordPath = Join-Path $artifactsDir "release-test-record-$Version.md"
  $checksText = if ($SkipChecks) { "Skipped by -SkipChecks" } else { "Passed through build-release.ps1" }
  @"
# Release Test Record

## Version

- Version: $Version
- Commit: $commit
- Date: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")
- Tester:

## Artifacts

- Local service package: nxjob-local-service-$Version.zip
- Browser extension package: nxjob-extension-$Version.zip
- Release manifest: release-manifest.json

## Automated Checks

- npm run shared:check: $checksText
- npm run extension:typecheck: $checksText
- python -m pytest apps/local-service/tests -q: $checksText
- scripts/package/build-release.ps1: Passed
- scripts/package/validate-release.ps1: Pending

## Manual Smoke Test

- Local service install script completed:
- scripts/start-local-service.ps1 -Background starts the service:
- scripts/check-health.ps1 returns ok:
- scripts/status-local-service.ps1 reports healthy:
- Browser extension loads:
- Analyze Sponsorship button works:
- Tailor Resume button creates a DOCX:
- Fill Form Answer drafts and fills only after confirmation:
- Outcome entry creates SuccessReference:
- scripts/stop-local-service.ps1 stops the service:
- scripts/uninstall-local-service.ps1 removes service files:

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
      "nxjob-local-service-$Version.zip",
      "nxjob-extension-$Version.zip",
      "release-manifest.json",
      "release-test-record-$Version.md"
    )
    checks = if ($SkipChecks) { "skipped" } else { "shared:check, extension:typecheck, pytest" }
    notes = "Windows-first MVP package. Private data is excluded."
  }
  $manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $artifactsDir "release-manifest.json") -Encoding UTF8

  if (-not $SkipValidation) {
    & (Join-Path $root "scripts\package\validate-release.ps1") -Version $Version -ArtifactsDir $artifactsDir
    (Get-Content -LiteralPath $recordPath -Raw).Replace("scripts/package/validate-release.ps1: Pending", "scripts/package/validate-release.ps1: Passed") | Set-Content -LiteralPath $recordPath -Encoding UTF8
  }
  Write-Host "Release artifacts written to $artifactsDir"
}
finally {
  Pop-Location
}
