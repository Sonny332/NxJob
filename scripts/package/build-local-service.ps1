param(
  [string]$Version = "0.7.0",
  [string]$ArtifactsDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not $ArtifactsDir) {
  $ArtifactsDir = Join-Path $root "releases\$Version"
}
$ArtifactsDir = [System.IO.Path]::GetFullPath($ArtifactsDir)
New-Item -ItemType Directory -Force -Path $ArtifactsDir | Out-Null
$stageRoot = Join-Path ([System.IO.Path]::GetTempPath()) "NxJobReleaseStage"
$stage = Join-Path $stageRoot "nxjob-local-service-$Version-$([System.Guid]::NewGuid().ToString('N'))"
$zipPath = Join-Path $ArtifactsDir "nxjob-local-service-$Version.zip"
$scriptSourceDir = Join-Path $root "scripts\package\local-service-scripts"
$rootScriptSourceDir = Join-Path $root "scripts\package\local-service-root-scripts"
. (Join-Path $PSScriptRoot "release-version.ps1")

function Update-LocalServicePackageVersion {
  param(
    [Parameter(Mandatory = $true)][string]$ServiceRoot,
    [Parameter(Mandatory = $true)][string]$PackageVersion
  )

  $pyprojectPath = Join-Path $ServiceRoot "pyproject.toml"
  $pyproject = Get-Content -LiteralPath $pyprojectPath -Raw
  $pyproject = $pyproject -replace '(?m)^(version\s*=\s*)"[^"]+"', "`$1`"$PackageVersion`""
  [System.IO.File]::WriteAllText($pyprojectPath, $pyproject, [System.Text.UTF8Encoding]::new($false))

  $initPath = Join-Path $ServiceRoot "src\nxjob\__init__.py"
  $init = Get-Content -LiteralPath $initPath -Raw
  $init = $init -replace '(?m)^(__version__\s*=\s*)"[^"]+"', "`$1`"$PackageVersion`""
  [System.IO.File]::WriteAllText($initPath, $init, [System.Text.UTF8Encoding]::new($false))
}

New-Item -ItemType Directory -Force -Path $stage | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "app") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "app\local-service") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "scripts") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "docs") | Out-Null

Copy-Item -LiteralPath (Join-Path $root "apps\local-service\pyproject.toml") -Destination (Join-Path $stage "app\local-service\pyproject.toml") -Force
$srcSource = Join-Path $root "apps\local-service\src"
$srcDestination = Join-Path $stage "app\local-service\src"
& robocopy $srcSource $srcDestination /E /XD __pycache__ /XF *.pyc *.pyo /NFL /NDL /NJH /NJS /NC /NS | Out-Null
if ($LASTEXITCODE -gt 7) {
  throw "robocopy failed while staging local service src with exit code $LASTEXITCODE."
}
Update-LocalServicePackageVersion -ServiceRoot (Join-Path $stage "app\local-service") -PackageVersion (Convert-ReleaseVersionToPythonPackageVersion -ReleaseVersion $Version)
Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination (Join-Path $stage "README.md") -Force
Copy-Item -LiteralPath (Join-Path $root "LICENSE") -Destination (Join-Path $stage "LICENSE") -Force
Copy-Item -LiteralPath (Join-Path $root "docs\install-windows.md") -Destination (Join-Path $stage "docs\install-windows.md") -Force
Copy-Item -LiteralPath (Join-Path $root "docs\master-resume-format.md") -Destination (Join-Path $stage "docs\master-resume-format.md") -Force
Copy-Item -LiteralPath (Join-Path $root "docs\privacy-boundary.md") -Destination (Join-Path $stage "docs\privacy-boundary.md") -Force
Copy-Item -Path (Join-Path $scriptSourceDir "*") -Destination (Join-Path $stage "scripts") -Force
Copy-Item -Path (Join-Path $rootScriptSourceDir "*.bat") -Destination $stage -Force
Set-Content -LiteralPath (Join-Path $stage "VERSION") -Value $Version -Encoding UTF8

if (Test-Path -LiteralPath $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -Force
try {
  Remove-Item -LiteralPath $stage -Recurse -Force
}
catch {
  Write-Warning "Could not remove local-service staging directory '$stage'. $($_.Exception.Message)"
}
Write-Host "Local service package: $zipPath"
