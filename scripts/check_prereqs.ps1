$ErrorActionPreference = 'Stop'
$missing = @()
foreach ($name in @('py', 'git', 'docker', 'kubectl')) {
    if (Get-Command $name -ErrorAction SilentlyContinue) {
        Write-Host "$name found"
    } else {
        $missing += $name
        Write-Warning "$name not found on PATH"
    }
}
if ($missing.Count -gt 0) {
    throw "Missing prerequisites: $($missing -join ', '). See README setup instructions."
}
& py -3.11 --version
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 is required.' }
& docker version
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop with Linux containers.' }
& kubectl --context docker-desktop get nodes
if ($LASTEXITCODE -ne 0) { throw 'Enable Kubernetes in Docker Desktop; do not reset existing clusters.' }