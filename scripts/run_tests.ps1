param([string]$Python = "$PSScriptRoot\..\.venv\Scripts\python.exe")
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $projectRoot
try {
    New-Item -ItemType Directory -Force test-results | Out-Null
    $testDirectory = 'test-results/tmp-' + [guid]::NewGuid().ToString('N')
    & $Python -m pytest --basetemp $testDirectory --cov --cov-branch --cov-fail-under=85 --cov-report=term-missing --cov-report=html:test-results/coverage --junitxml=test-results/results.xml
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
}
finally { Pop-Location }
