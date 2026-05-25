<#
.SYNOPSIS
Runs the local-service pytest suite through the NxJob pytest wrapper.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-local-service.ps1

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-local-service.ps1 apps/local-service/tests/api/test_m6_form_answer.py -q
#>

param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$PytestArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$PytestArgs = @($PytestArgs | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
$pythonPaths = @((Join-Path $repoRoot "apps\local-service\src"))
$candidateDepsPaths = @(
  (Join-Path $repoRoot ".python-deps"),
  (Join-Path (Split-Path (Split-Path $repoRoot -Parent) -Parent) "NxJob\.python-deps")
)

foreach ($depsPath in $candidateDepsPaths) {
  if (Test-Path -LiteralPath $depsPath) {
    $pythonPaths = @($depsPath) + $pythonPaths
    break
  }
}

$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPATH = ($pythonPaths -join [System.IO.Path]::PathSeparator)

$testRuntimeDir = Join-Path ([System.IO.Path]::GetTempPath()) ("NxJobLocalServiceTest\" + [System.Guid]::NewGuid().ToString("N"))
$testLocalAppDataDir = Join-Path $testRuntimeDir "localappdata"
$testGeneratedResumeDir = Join-Path $testRuntimeDir "generated-resumes"
New-Item -ItemType Directory -Force -Path $testLocalAppDataDir | Out-Null
New-Item -ItemType Directory -Force -Path $testGeneratedResumeDir | Out-Null

$env:LOCALAPPDATA = $testLocalAppDataDir
$env:NXJOB_DB_PATH = Join-Path $testRuntimeDir "nxjob-test.sqlite3"
$env:NXJOB_GENERATED_RESUME_DIR = $testGeneratedResumeDir

if ($PytestArgs.Count -eq 0) {
  $PytestArgs = @("apps\local-service\tests", "-q", "--tb=short")
}

& (Join-Path $PSScriptRoot "run_pytest.ps1") @PytestArgs
exit $LASTEXITCODE
