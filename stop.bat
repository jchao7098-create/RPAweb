@echo off
title RPA Stop

echo.
echo  ============================================
echo    Stopping RPA services...
echo  ============================================
echo.

echo Stopping backend (port 5090)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5090 " ^| findstr "LISTENING" 2^>nul') do (
    echo    Killing PID: %%a
    taskkill /pid %%a /f >nul 2>&1
)

echo Stopping frontend (port 8090)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8090 " ^| findstr "LISTENING" 2^>nul') do (
    echo    Killing PID: %%a
    taskkill /pid %%a /f >nul 2>&1
)

echo Closing service windows...
taskkill /fi "WINDOWTITLE eq RPA-Backend" /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq RPA-Frontend" /f >nul 2>&1

echo.
echo All services stopped.
echo.
pause
