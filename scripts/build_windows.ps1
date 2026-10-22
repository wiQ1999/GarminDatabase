param([string]$Python = "$PSScriptRoot\..\.venv\Scripts\python.exe", [string]$Destination = "$PSScriptRoot\..\dist")
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $projectRoot
try {
    $resourceArgument = (Join-Path $projectRoot 'garmin_database/resources') + ';garmin_database/resources'
    & $Python -m PyInstaller --noconfirm --onedir --windowed --name GarminDatabase --distpath $Destination --specpath build --collect-data garmin_database --collect-data garmin_fit_sdk --collect-data fitdecode --collect-data tzdata --copy-metadata garminconnect --copy-metadata fitdecode --copy-metadata garmin-fit-sdk --add-data $resourceArgument desktop.py
    if ($LASTEXITCODE -ne 0) { throw 'Windows build failed' }
    # Qt 6.12 uses Windows 11's unversioned ICU API. The bundled development
    # runtime puts ICU 78 on PATH; its suffixed exports break QtCore at startup.
    # These two accidentally collected root DLLs must not shadow system ICU.
    $bundleDirectory = Join-Path $Destination 'GarminDatabase/_internal'
    foreach ($library in @('icuuc.dll', 'icudt78.dll')) {
        $libraryPath = Join-Path $bundleDirectory $library
        if (Test-Path -LiteralPath $libraryPath) { Remove-Item -LiteralPath $libraryPath }
    }
    & $Python -m PyInstaller --noconfirm --onedir --console --name GarminDatabaseMCP --distpath $Destination --specpath build --collect-data garmin_database --collect-data garmin_fit_sdk --collect-data tzdata --copy-metadata mcp --copy-metadata anyio --hidden-import anyio._backends._asyncio --exclude-module PySide6 --exclude-module garminconnect mcp_stdio.py
    if ($LASTEXITCODE -ne 0) { throw 'Windows MCP build failed' }
    Write-Output (Join-Path $Destination 'GarminDatabase/GarminDatabase.exe')
    Write-Output (Join-Path $Destination 'GarminDatabaseMCP/GarminDatabaseMCP.exe')
}
finally { Pop-Location }
