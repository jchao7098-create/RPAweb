@echo off
title RPA Deploy

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"

echo.
echo  ============================================
echo    RPA Deploy - Starting...
echo  ============================================
echo.

echo [1/5] Checking environment...
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.12+
    echo         https://www.python.org/downloads/
    goto :fail
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo         %%i

where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install Node.js 20+
    echo         https://nodejs.org/
    goto :fail
)
for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo         %%i

echo.
echo [2/5] Preparing backend...

if not exist "%BACKEND%\venv\Scripts\python.exe" (
    echo         Creating venv...
    python -m venv "%BACKEND%\venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create venv
        goto :fail
    )
)

echo         Installing Python packages...
call "%BACKEND%\venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r "%BACKEND%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] pip install failed
    goto :fail
)

echo.
echo [3/5] Preparing frontend...

cd /d "%FRONTEND%"

if not exist "node_modules" (
    echo         Installing npm packages...
    call npm config set registry https://registry.npmmirror.com >nul 2>&1
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed
        goto :fail
    )
)

echo         Detecting server IP...
set "SERVER_IP=127.0.0.1"
for /f "tokens=*" %%a in ('ipconfig ^| findstr /i "172.16." ^| findstr "IPv4"') do call :parse_ip "%%a"
if not "%SERVER_IP%"=="127.0.0.1" goto :got_ip
for /f "tokens=*" %%a in ('ipconfig ^| findstr "IPv4" ^| findstr /v "127.0.0"') do call :parse_ip "%%a"
:got_ip
echo         Server IP: %SERVER_IP%

echo.
echo [4/5] Building frontend...

set "VITE_API_BASE_URL=http://%SERVER_IP%:5090"
set "PASSWORD_RESET_FRONTEND_URL=http://%SERVER_IP%:8090"
echo         API URL: %VITE_API_BASE_URL%
echo         Password reset URL: %PASSWORD_RESET_FRONTEND_URL%

call npm run build
if errorlevel 1 (
    echo [ERROR] Build failed
    goto :fail
)

cd /d "%ROOT%"

echo.
echo [5/5] Starting services...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5090 " ^| findstr "LISTENING" 2^>nul') do (
    taskkill /pid %%a /f >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8090 " ^| findstr "LISTENING" 2^>nul') do (
    taskkill /pid %%a /f >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo         Backend on port 5090...
start "RPA-Backend" cmd /k "cd /d "%BACKEND%" && "%BACKEND%\venv\Scripts\python.exe" run.py"

echo         Frontend on port 8090...
start "RPA-Frontend" cmd /k "cd /d "%FRONTEND%" && npx vite preview --port 8090 --host 0.0.0.0"

timeout /t 3 /nobreak >nul

echo.
echo  ============================================
echo   Deploy Done!
echo  ============================================
echo.
echo   Local:    http://127.0.0.1:8090
echo   LAN:      http://%SERVER_IP%:8090
echo.
echo   Close the 2 service windows to stop.
echo.
echo Press any key to open browser...
pause >nul
start http://127.0.0.1:8090
exit /b 0

:parse_ip
for /f "tokens=2 delims=:" %%x in ("%~1") do set "SERVER_IP=%%x"
set "SERVER_IP=%SERVER_IP: =%"
goto :eof

:fail
echo.
echo Press any key to exit...
pause >nul
exit /b 1
