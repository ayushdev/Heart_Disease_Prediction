param([switch]$SkipDownload)
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    $python = Join-Path $PWD '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) { throw 'Create .venv and install requirements first.' }
    function Invoke-Python {
        param([string[]]$Arguments)
        & $python @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Python step failed: $($Arguments -join ' ')" }
    }
    Invoke-Python -Arguments @('-m', 'ruff', 'check', '.')
    Invoke-Python -Arguments @('-m', 'ruff', 'format', '--check', '.')
    Invoke-Python -Arguments @('-m', 'pytest', 'test', '-q', '--junitxml=reports/tests.xml', '--cov=heart_risk', '--cov-report=xml')
    if (-not $SkipDownload) { Invoke-Python -Arguments @('-m', 'heart_risk.data') }
    Invoke-Python -Arguments @('-m', 'heart_risk.eda')
    Invoke-Python -Arguments @('-m', 'heart_risk.train')
    Invoke-Python -Arguments @('scripts/build_report.py')
} finally {
    Pop-Location
}