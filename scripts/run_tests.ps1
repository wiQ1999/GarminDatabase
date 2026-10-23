param([string]$Python = "$PSScriptRoot\..\.venv\Scripts\python.exe")
$ErrorActionPreference = 'Stop'
& $Python (Join-Path $PSScriptRoot 'run_tests.py')
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
