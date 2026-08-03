param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8188
)

$ErrorActionPreference = 'Stop'

if ($Port -in 5090, 8090) {
    throw "Port $Port belongs to the existing website and cannot be used for deployment testing."
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root 'backend'
$frontendIndex = Join-Path $root 'frontend\dist\index.html'
$python = Join-Path $backend 'venv\Scripts\python.exe'
$pidFile = Join-Path $backend "var\server-test-$Port.pid"
$stdoutLog = Join-Path $backend "var\server-test-$Port.out.log"
$stderrLog = Join-Path $backend "var\server-test-$Port.err.log"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtual environment was not found: $python"
}
if (-not (Test-Path -LiteralPath $frontendIndex)) {
    throw "The built frontend was not found: $frontendIndex"
}

$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port $Port is already occupied by PID $($listener[0].OwningProcess)."
}

$env:INTRANET_PORT = [string]$Port
$env:INTRANET_PUBLIC_URL = "http://172.16.50.20:$Port"

$process = Start-Process `
    -FilePath $python `
    -ArgumentList 'run_intranet.py' `
    -WorkingDirectory $backend `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -WindowStyle Hidden `
    -PassThru

$process.Id | Set-Content -LiteralPath $pidFile -Encoding ascii
Start-Sleep -Seconds 3

if ($process.HasExited) {
    throw "The deployment-test service exited during startup. See $stderrLog"
}

$response = Invoke-WebRequest `
    -Uri "http://127.0.0.1:$Port/public/ping" `
    -UseBasicParsing `
    -TimeoutSec 10
if ($response.StatusCode -ne 200) {
    throw "The deployment-test health check returned HTTP $($response.StatusCode)."
}

Write-Host "Deployment-test site: http://172.16.50.20:$Port/"
Write-Host 'Existing ports 5090 and 8090 were not changed.'
