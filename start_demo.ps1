# Project Sentinel - Quick Demo Launcher (PowerShell)
# This script starts all demo components

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Project Sentinel - Demo Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Starting API Server..." -ForegroundColor Yellow
Start-Process -FilePath "py" -ArgumentList "src/integration/api_server.py --seed-demo --log-level INFO" -WindowStyle Normal
Start-Sleep -Seconds 3

Write-Host "[2/3] Opening Dashboard..." -ForegroundColor Yellow
Start-Process "src/dashboard/simple_dashboard.html"
Start-Sleep -Seconds 2

Write-Host "[3/3] All components started!" -ForegroundColor Green
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DEMO READY!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "API Server: http://localhost:5000" -ForegroundColor White
Write-Host "Dashboard: Opened in browser" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C in the API Server window to stop" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
