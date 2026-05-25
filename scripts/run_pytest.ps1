<#
.SYNOPSIS
Runs pytest through the NxJob Windows-safe test harness.

.DESCRIPTION
Use this wrapper instead of calling `python -m pytest` directly from Codex
sub-agents or Claude workers. Python 3.14 on the current Windows worker host can
create pytest temporary directories with unusable ACLs when pytest requests
0o700 directories. The Python runner patches that process-local mkdir behavior
before importing pytest and keeps runtime files under the Windows temp folder.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_pytest.ps1 apps/local-service/tests -q
#>

param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$PytestArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$runner = Join-Path $PSScriptRoot "run_pytest.py"
$runtimeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("NxJobPytest\" + [System.Guid]::NewGuid().ToString("N"))
$PytestArgs = @($PytestArgs | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $python -PathType Leaf) {
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  & $python -c "import pytest" *> $null
  $venvHasPytest = ($LASTEXITCODE -eq 0)
  $ErrorActionPreference = $previousErrorActionPreference
  if (-not $venvHasPytest) {
    $python = "python"
  }
}
else {
  $python = "python"
}

if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
  throw "NxJob pytest runner not found: $runner"
}

New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
$env:NXJOB_PYTEST_RUNTIME_ROOT = $runtimeRoot

Push-Location $repoRoot
try {
  & $python $runner @PytestArgs
  exit $LASTEXITCODE
}
finally {
  Pop-Location
}
