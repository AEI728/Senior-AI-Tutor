$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$pythonPath=Join-Path $projectRoot 'apps/api/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run uv sync --frozen in apps/api first (Python 3.12+).' }
Set-Location -LiteralPath $projectRoot
& $pythonPath scripts/tasks.py local
