param([string]$Python = "$PSScriptRoot\..\.venv\Scripts\python.exe", [string]$Destination = "$PSScriptRoot\..\dist")
$ErrorActionPreference = 'Stop'
& $Python (Join-Path $PSScriptRoot 'build.py') --destination $Destination
if ($LASTEXITCODE -ne 0) { throw 'Windows build failed' }
Write-Output (Join-Path $Destination 'GarminDatabase/GarminDatabase.exe')
Write-Output (Join-Path $Destination 'GarminDatabaseMCP/GarminDatabaseMCP.exe')
