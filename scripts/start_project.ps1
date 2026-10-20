param(
    [int]$ApiPort = 8000,
    [int]$MlflowPort = 5000
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$model = Join-Path $root 'models\metadata.json'
$logs = Join-Path $root 'reports'

if (-not (Test-Path $python)) { throw 'Missing .venv. Follow the Clean Setup steps in README.md first.' }
if (-not (Test-Path $model)) { throw 'Missing models/metadata.json. Run .\scripts\run_pipeline.ps1 first.' }
if ($ApiPort -notin 1..65535 -or $MlflowPort -notin 1..65535) { throw 'Ports must be between 1 and 65535.' }
New-Item -ItemType Directory -Path $logs -Force | Out-Null

function Test-Endpoint {
    param([string]$Url)
    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.UseProxy = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    try {
        $client.Timeout = [TimeSpan]::FromSeconds(2)
        $response = $client.GetAsync($Url).GetAwaiter().GetResult()
        return $response.StatusCode -eq [System.Net.HttpStatusCode]::OK
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Test-PortInUse {
    param([int]$Port)
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Start-ServiceIfNeeded {
    param(
        [string]$Name,
        [string]$Url,
        [int]$Port,
        [string]$Arguments,
        [string]$LogName
    )
    if (Test-Endpoint $Url) {
        Write-Host "$Name already responds at $Url"
        return
    }
    if (Test-PortInUse $Port) { throw "Port $Port is already in use, but $Name did not respond at $Url. No process was stopped." }

    $stdout = Join-Path $logs "$LogName.out.log"
    $stderr = Join-Path $logs "$LogName.err.log"
    $process = Start-Process -FilePath $python -ArgumentList $Arguments -WorkingDirectory $root `
        -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($process.HasExited) {
            $details = if (Test-Path $stderr) { Get-Content $stderr -Raw } else { '' }
            throw "$Name exited during startup. $details"
        }
        if (Test-Endpoint $Url) {
            Write-Host "Started $Name at $Url (PID $($process.Id))"
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw "$Name did not become ready within 60 seconds. Check $stderr"
}

Start-ServiceIfNeeded -Name 'Local FastAPI' -Url "http://127.0.0.1:$ApiPort/readyz" -Port $ApiPort `
    -Arguments "-m uvicorn heart_risk.api:app --host 127.0.0.1 --port $ApiPort --no-access-log" -LogName 'api'
Start-ServiceIfNeeded -Name 'MLflow' -Url "http://127.0.0.1:$MlflowPort/health" -Port $MlflowPort `
    -Arguments "-m mlflow server --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port $MlflowPort --no-serve-artifacts" -LogName 'mlflow'

Write-Host ''
Write-Host "Local API:  http://localhost:$ApiPort/docs"
Write-Host "MLflow:     http://localhost:$MlflowPort"
Write-Host 'Deployed Kubernetes API (if enabled): http://localhost:8080/docs'