$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontend = Join-Path $root 'frontend'
$backend = Join-Path $root 'backend'
$python = Join-Path $backend 'venv\Scripts\python.exe'
$port = 8088
$pidFile = Join-Path $backend 'var\intranet-8088.pid'
$stdoutLog = Join-Path $backend 'var\intranet-8088.out.log'
$stderrLog = Join-Path $backend 'var\intranet-8088.err.log'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Backend virtual environment not found: $python"
}

$listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port $port is already occupied by PID $($listener[0].OwningProcess)."
}

Push-Location $frontend
try {
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) {
        throw 'Frontend build failed.'
    }
}
finally {
    Pop-Location
}

$process = Start-Process `
    -FilePath $python `
    -ArgumentList 'run_intranet.py' `
    -WorkingDirectory $backend `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -WindowStyle Hidden `
    -PassThru

$process.Id | Set-Content -LiteralPath $pidFile -Encoding ascii
Start-Sleep -Seconds 2

if ($process.HasExited) {
    throw "Intranet service exited during startup. See $stderrLog"
}

$ip = Get-NetIPAddress -AddressFamily IPv4 -AddressState Preferred |
    Where-Object { $_.IPAddress -like '172.16.*' } |
    Select-Object -First 1 -ExpandProperty IPAddress
if (-not $ip) {
    $ip = '127.0.0.1'
}

Write-Host "Intranet site: http://${ip}:$port/"
Write-Host 'The existing port 8090 service was not changed.'
