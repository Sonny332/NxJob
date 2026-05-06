Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$extension = Join-Path $root "apps\extension"

Set-Location $extension
npm run dev

