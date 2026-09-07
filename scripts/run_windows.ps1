param(
  [string]$HostName = $(if ($env:MEDRAY_HOST) { $env:MEDRAY_HOST } else { "127.0.0.1" }),
  [int]$BackendStartPort = $(if ($env:MEDRAY_PORT) { [int]$env:MEDRAY_PORT } else { 8765 }),
  [int]$FrontendStartPort = $(if ($env:MEDRAY_FRONTEND_PORT) { [int]$env:MEDRAY_FRONTEND_PORT } else { 5173 })
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
try {
  if (!(Test-Path ".venv\Scripts\python.exe") -or !(Test-Path "frontend\node_modules")) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\setup_windows.ps1"
    if ($LASTEXITCODE -ne 0) { throw "Setup did not finish. Run setup_medray_v2.bat first." }
  }
  & (Join-Path $ProjectRoot ".venv\Scripts\python.exe") "scripts\launch.py" --host $HostName --backend-port $BackendStartPort --frontend-port $FrontendStartPort
  exit $LASTEXITCODE
} catch {
  Write-Host "MedRay could not start: $($_.Exception.Message)"
  Write-Host "Run setup_medray_v2.bat and follow its instructions, then retry."
  exit 1
}
