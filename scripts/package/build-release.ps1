param(
  [string]$Version = "0.1.0",
  [switch]$SkipChecks
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

  $manifest = [ordered]@{
    version = $Version
    commit = $commit
    created_at = (Get-Date).ToString("o")
    artifacts = @(
      "nxjob-local-service-$Version.zip",
      "nxjob-extension-$Version.zip"
    )
    checks = if ($SkipChecks) { "skipped" } else { "shared:check, extension:typecheck, pytest" }
    notes = "Windows-first MVP package. Private data is excluded."
  }
  $manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $artifactsDir "release-manifest.json") -Encoding UTF8
  Write-Host "Release artifacts written to $artifactsDir"
}
finally {
  Pop-Location
}
