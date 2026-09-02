param(
    [string]$HostName = $(if ($env:MEDRAY_HOST) { $env:MEDRAY_HOST } else { "127.0.0.1" }),
    [int]$BackendStartPort = $(if ($env:MEDRAY_PORT) { [int]$env:MEDRAY_PORT } else { 8765 }),
    [int]$FrontendStartPort = $(if ($env:MEDRAY_FRONTEND_PORT) { [int]$env:MEDRAY_FRONTEND_PORT } else { 5173 })
)

if ($HostName -notin @("127.0.0.1", "localhost")) {
    throw "Without authentication, the MedRay backend may bind only to loopback: HostName=$HostName"
}

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}
if (-not (Test-Path ".venv") -or -not (Test-Path "frontend\node_modules")) {
    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\setup_windows.ps1"
}

function Test-PortAvailable {
    param([string]$HostName, [int]$Port)
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse($HostName), $Port)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) {
            $listener.Stop()
        }
    }
}

function Get-FreePort {
    param([string]$HostName, [int]$StartPort, [int]$Count)
    for ($port = $StartPort; $port -lt ($StartPort + $Count); $port++) {
        if (Test-PortAvailable -HostName $HostName -Port $port) {
            return $port
        }
    }
    throw "No free port was found from $StartPort through $($StartPort + $Count - 1)."
}

function Start-MedRayProcess {
    param(
        [string]$FileName,
        [string]$Arguments,
        [string]$WorkingDirectory
    )
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FileName
    $psi.Arguments = $Arguments
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi
    [void]$process.Start()
    return $process
}

function Stop-MedRayProcessTree {
    param([System.Diagnostics.Process]$Process)
    if (-not $Process) {
        return
    }
    try {
        if (-not $Process.HasExited) {
            & taskkill.exe /PID $Process.Id /T /F 2>$null | Out-Null
            if ($LASTEXITCODE -ne 0 -and -not $Process.HasExited) {
                Stop-Process -Id $Process.Id -Force -ErrorAction Stop
            }
        }
    } catch {
        Write-Warning "Could not stop PID $($Process.Id): $($_.Exception.Message)"
    }
}

$backend = $null
$frontend = $null

try {
    $backendPort = Get-FreePort -HostName $HostName -StartPort $BackendStartPort -Count 50
    $frontendPort = Get-FreePort -HostName $HostName -StartPort $FrontendStartPort -Count 20
    $apiBase = "http://${HostName}:${backendPort}/api"

    $backend = Start-MedRayProcess `
        -FileName (Join-Path $ProjectRoot ".venv\Scripts\python.exe") `
        -Arguments "-m uvicorn app.main:app --host $HostName --port $backendPort --app-dir backend" `
        -WorkingDirectory $ProjectRoot

    Write-Host "Waiting for the backend at $apiBase/health ..."
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        if ($backend.HasExited) {
            throw "The backend stopped before it was ready. Exit code: $($backend.ExitCode)"
        }
        try {
            Invoke-RestMethod -Uri "$apiBase/health" -TimeoutSec 1 | Out-Null
            $ready = $true
            break
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $ready) {
        throw "The backend was not ready after 20 seconds."
    }

    $frontend = Start-MedRayProcess `
        -FileName "cmd.exe" `
        -Arguments "/c set VITE_API_BASE=$apiBase&& npm run dev -- --host $HostName --port $frontendPort --strictPort" `
        -WorkingDirectory (Join-Path $ProjectRoot "frontend")

    Write-Host ""
    Write-Host "MedRay v2 is running."
    Write-Host "Frontend: http://${HostName}:${frontendPort}"
    Write-Host "Backend:  $apiBase/health"
    Write-Host ""
    Write-Host "Close this window or press Ctrl+C to stop both services and release their ports."

    while ($true) {
        if ($backend.HasExited) {
            throw "The backend stopped. Exit code: $($backend.ExitCode)"
        }
        if ($frontend.HasExited) {
            throw "The frontend stopped. Exit code: $($frontend.ExitCode)"
        }
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host ""
    Write-Host "Stopping MedRay v2 and releasing ports..."
    Stop-MedRayProcessTree -Process $frontend
    Stop-MedRayProcessTree -Process $backend
}
