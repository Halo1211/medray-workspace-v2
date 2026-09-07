@echo off
setlocal EnableExtensions
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
if errorlevel 1 (
  echo Setup did not finish. Read the message above, fix the missing component, and retry.
  pause
  exit /b 1
)
echo Setup complete. Double-click start_medray_v2.bat.
pause
