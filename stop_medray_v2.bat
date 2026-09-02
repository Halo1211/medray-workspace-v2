@echo off
setlocal EnableExtensions
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\stop_windows.ps1
