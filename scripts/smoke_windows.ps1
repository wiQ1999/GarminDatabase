param([string]$Executable = "$PSScriptRoot\..\dist\GarminDatabase\GarminDatabase.exe", [string]$Python = "$PSScriptRoot\..\.venv\Scripts\python.exe")
$ErrorActionPreference = 'Stop'
& $Python (Join-Path $PSScriptRoot 'smoke.py') $Executable
if ($LASTEXITCODE -ne 0) { throw 'Packaged Windows smoke test failed' }
