@echo off
REM Project Sentinel - Quick Demo Launcher
REM This script starts all demo components

echo ========================================
echo Project Sentinel - Demo Launcher
echo ========================================
echo.

echo [1/3] Starting API Server...
start "API Server" py src/integration/api_server.py --seed-demo --log-level INFO
timeout /t 3 /nobreak >nul

echo [2/3] Opening Dashboard...
start "" "src/dashboard/simple_dashboard.html"
timeout /t 2 /nobreak >nul

echo [3/3] All components started!
echo.
echo ========================================
echo DEMO READY!
echo ========================================
echo API Server: http://localhost:5000
echo Dashboard: Opened in browser
echo.
echo Press Ctrl+C in the API Server window to stop
echo ========================================
pause
