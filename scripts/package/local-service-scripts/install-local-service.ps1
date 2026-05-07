param(
  [string]$InstallRoot = "",
  [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

function Get-PackageVersion {
  $versionFile = Join-Path $PSScriptRoot "..\VERSION"
  if (Test-Path -LiteralPath $versionFile) {
    return (Get-Content -LiteralPath $versionFile -TotalCount 1).Trim()
  }
  return "unknown"
}

if ([System.Environment]::OSVersion.Platform -ne "Win32NT") {
  throw "This MVP installer is Windows-only."
}

if (-not $InstallRoot) {
  if (-not $env:LOCALAPPDATA) {
    throw "LOCALAPPDATA is not set. Pass -InstallRoot explicitly."
  }
  $InstallRoot = Join-Path $env:LOCALAPPDATA "NxJob\LocalService"
}

$sourceRoot = Join-Path $PSScriptRoot "..\app\local-service"
$packageRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$installedServiceRoot = Join-Path $InstallRoot "app\local-service"
$venv = Join-Path $InstallRoot ".venv"
$pythonCommand = Get-Command python -ErrorAction Stop
$versionText = (& $pythonCommand.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($LASTEXITCODE -ne 0) {
  throw "Unable to verify Python version."
}
if ([version]$versionText -lt [version]"3.11") {
  throw "Python 3.11 or newer is required. Found Python $versionText."
}

if ((Test-Path -LiteralPath $InstallRoot) -and -not $Force) {
  Write-Host "Updating existing NxJob Local Service at $InstallRoot"
}

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot "logs") | Out-Null
New-Item -ItemType Directory -Force -Path $installedServiceRoot | Out-Null
Copy-Item -Path (Join-Path $sourceRoot "*") -Destination $installedServiceRoot -Recurse -Force
Copy-Item -LiteralPath (Join-Path $packageRoot "README.md") -Destination (Join-Path $InstallRoot "README.md") -Force
Copy-Item -LiteralPath (Join-Path $packageRoot "LICENSE") -Destination (Join-Path $InstallRoot "LICENSE") -Force

Push-Location $installedServiceRoot
try {
  if (-not (Test-Path -LiteralPath $venv)) {
    Invoke-Checked $pythonCommand.Source -m venv $venv
  }
  $venvPython = Join-Path $venv "Scripts\python.exe"
  Invoke-Checked $venvPython -m pip install --upgrade pip
  Invoke-Checked $venvPython -m pip install .
}
finally {
  Pop-Location
}

$state = [ordered]@{
  version = Get-PackageVersion
  install_root = $InstallRoot
  service_root = $installedServiceRoot
  installed_at = (Get-Date).ToString("o")
  python = (Join-Path $venv "Scripts\python.exe")
}
$state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $InstallRoot "install-state.json") -Encoding UTF8

Write-Host "NxJob Local Service installed at $InstallRoot"
Write-Host "Start it with scripts\start-local-service.ps1 -Background"
