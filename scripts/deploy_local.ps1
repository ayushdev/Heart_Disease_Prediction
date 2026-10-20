param(
    [Parameter(Mandatory=$true)][string]$ReleaseManifest,
    [string]$ImagePullSecret = ''
)
$ErrorActionPreference = 'Stop'
$ReleaseManifest = (Resolve-Path $ReleaseManifest).Path
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    $python = Join-Path $PWD '.venv\Scripts\python.exe'
    function Invoke-Kube {
        param([string[]]$Arguments)
        $result = & kubectl --context docker-desktop @Arguments
        if ($LASTEXITCODE -ne 0) { throw "kubectl failed: $($Arguments -join ' ')" }
        return $result
    }
    Invoke-Kube -Arguments @('get', 'nodes')
    $release = Get-Content $ReleaseManifest -Raw | ConvertFrom-Json
    $renderArgs = @('scripts/release.py', '--render', $ReleaseManifest, '--output', 'reports/evidence/deployment.yaml')
    if ($ImagePullSecret) { $renderArgs += @('--pull-secret', $ImagePullSecret) }
    & $python @renderArgs
    if ($LASTEXITCODE -ne 0) { throw 'Release manifest validation failed.' }
    Invoke-Kube -Arguments @('apply', '-f', 'reports/evidence/deployment.yaml')
    Invoke-Kube -Arguments @('-n', 'heart-risk', 'rollout', 'status', 'deployment/heart-risk-api', '--timeout=180s')
    Invoke-Kube -Arguments @('-n', 'heart-risk', 'wait', 'service/heart-risk-api', '--for=jsonpath={.status.loadBalancer.ingress}', '--timeout=120s')
    & $python scripts/verify_api.py --url http://localhost:8080 --expected-version $release.model_version --output reports/evidence/kubernetes.json
    if ($LASTEXITCODE -ne 0) { throw 'LoadBalancer prediction smoke test failed.' }
    $configFiles = @{
        'prometheus-config' = 'monitoring/prometheus.yml'
        'grafana-datasource' = 'monitoring/grafana/datasource.yml'
        'grafana-provider' = 'monitoring/grafana/provider.yml'
        'grafana-dashboard' = 'monitoring/grafana/dashboard.json'
    }
    foreach ($name in $configFiles.Keys) {
        $definition = Invoke-Kube -Arguments @('-n', 'heart-risk', 'create', 'configmap', $name, "--from-file=$($configFiles[$name])", '--dry-run=client', '-o', 'json')
        $definition | & kubectl --context docker-desktop apply -f -
        if ($LASTEXITCODE -ne 0) { throw "Failed to apply ConfigMap $name" }
    }
    Invoke-Kube -Arguments @('-n', 'heart-risk', 'get', 'secret', 'grafana-admin', '-o', 'name')
    Invoke-Kube -Arguments @('apply', '-f', 'deploy/k8s/monitoring.yaml')
    foreach ($name in @('prometheus', 'grafana')) {
        Invoke-Kube -Arguments @('-n', 'heart-risk', 'rollout', 'status', "deployment/$name", '--timeout=180s')
    }
    Invoke-Kube -Arguments @('-n', 'heart-risk', 'get', 'deployments,pods,services', '-o', 'json') |
        Set-Content -Encoding UTF8 reports/evidence/kubernetes-resources.json
    Invoke-Kube -Arguments @('-n', 'heart-risk', 'logs', '-l', 'app=heart-risk-api', '--prefix=true', '--tail=100') |
        Set-Content -Encoding UTF8 reports/evidence/kubernetes-api.log
    Write-Host 'API verified at http://localhost:8080/docs. See README for monitoring port-forwards.'
} finally {
    Pop-Location
}