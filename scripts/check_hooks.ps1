Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$settingsPath = Join-Path $repoRoot ".claude\settings.json"

$settingsExists = Test-Path -LiteralPath $settingsPath -PathType Leaf
$settingsParsed = $false
$hooksConfigured = $false
$parseError = ""
$hookKeys = @()

if ($settingsExists) {
  try {
    $settings = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $settingsParsed = $true
    $hooksProperty = $settings.PSObject.Properties["hooks"]
    if ($null -ne $hooksProperty -and $null -ne $hooksProperty.Value) {
      $hooksConfigured = $true
      $hookKeys = @($hooksProperty.Value.PSObject.Properties.Name)
    }
  }
  catch {
    $parseError = $_.Exception.Message
  }
}

$report = [ordered]@{
  repoRoot = $repoRoot
  settingsPath = $settingsPath
  mode = "read-only"
  settingsExists = $settingsExists
  settingsParsed = $settingsParsed
  hooksConfigured = $hooksConfigured
  hookKeys = $hookKeys
  parseError = $parseError
}

Write-Host ("Repo root: {0}" -f $repoRoot)
Write-Host ("mode: {0}" -f $report.mode)
Write-Host (".claude/settings.json exists: {0}" -f $settingsExists)
Write-Host ("hooks configured: {0}" -f $hooksConfigured)
if ($hookKeys.Count -gt 0) {
  Write-Host ("hook keys: {0}" -f ($hookKeys -join ", "))
}
if (-not [string]::IsNullOrWhiteSpace($parseError)) {
  Write-Host ("parse error: {0}" -f $parseError)
}

$report | ConvertTo-Json -Depth 6
