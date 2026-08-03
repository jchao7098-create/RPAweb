param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8188
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $root "backend\var\server-test-$Port.pid"

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host "No deployment-test PID file was found for port $Port."
    exit 0
}

$servicePid = [int](Get-Content -LiteralPath $pidFile)
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $servicePid"
if (-not $process) {
    Write-Host "The recorded deployment-test process for port $Port is no longer running."
    exit 0
}
if ($process.CommandLine -notlike '*run_intranet.py*') {
    throw "PID $servicePid does not belong to run_intranet.py; it was not stopped."
}

Stop-Process -Id $servicePid
Write-Host "Stopped the deployment-test service on port $Port (PID $servicePid)."
