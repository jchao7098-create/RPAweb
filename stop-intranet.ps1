$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $root 'backend\var\intranet-8088.pid'

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host 'No intranet PID file was found.'
    exit 0
}

$servicePid = [int](Get-Content -LiteralPath $pidFile)
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $servicePid"
if (-not $process) {
    Write-Host 'The recorded intranet process is no longer running.'
    exit 0
}
if ($process.CommandLine -notlike '*run_intranet.py*') {
    throw "PID $servicePid does not belong to run_intranet.py; it was not stopped."
}

Stop-Process -Id $servicePid
Write-Host "Stopped the intranet service (PID $servicePid)."
