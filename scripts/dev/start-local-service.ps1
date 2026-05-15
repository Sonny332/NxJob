Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$service = Join-Path $root "apps\local-service"

Set-Location $service
python -m uvicorn nxjob.main:app --app-dir src --host 127.0.0.1 --port 8765 --reload

