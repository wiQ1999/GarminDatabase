param([string]$Executable = "$PSScriptRoot\..\dist\GarminDatabase\GarminDatabase.exe")
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$resultDirectory = Join-Path $projectRoot 'test-results/packaged-smoke'
New-Item -ItemType Directory -Force $resultDirectory | Out-Null
$picturePath = Join-Path $resultDirectory 'start.png'
$errorPath = Join-Path $resultDirectory 'start.error.json'
if (Test-Path -LiteralPath $picturePath) { Remove-Item -LiteralPath $picturePath }
if (Test-Path -LiteralPath $errorPath) { Remove-Item -LiteralPath $errorPath }
$env:QT_QPA_PLATFORM = 'offscreen'
$processArguments = @('--data-dir', ('"' + (Join-Path $resultDirectory 'data') + '"'), '--settings-file', ('"' + (Join-Path $resultDirectory 'settings.json') + '"'), '--smoke-screenshot', ('"' + $picturePath + '"'))
$process = Start-Process -FilePath $Executable -WorkingDirectory $projectRoot -ArgumentList $processArguments -WindowStyle Hidden -PassThru
if (-not $process.WaitForExit(20000)) {
    Stop-Process -Id $process.Id
    throw 'Packaged application did not exit during smoke test'
}
if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $picturePath)) {
    if (Test-Path -LiteralPath $errorPath) { Get-Content -LiteralPath $errorPath }
    throw 'Packaged application failed smoke test'
}
Write-Output 'Packaged Windows smoke test passed'
