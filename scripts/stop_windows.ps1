param(
    [int[]]$BackendPorts = @(8765..8815),
    [int[]]$FrontendPorts = @(5173..5193)
)

$ErrorActionPreference = "Continue"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ports = @($BackendPorts + $FrontendPorts | Sort-Object -Unique)
$connections = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $ports -contains $_.LocalPort }

if (-not $connections) {
    Write-Host "No MedRay process is listening on the default port ranges."
    exit 0
}

$pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pidValue in $pids) {
    $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if (-not $process) {
        continue
    }
    $path = [string]($process.Path)
    $commandLine = ""
    try {
        $commandLine = [string](Get-CimInstance Win32_Process -Filter "ProcessId=$pidValue").CommandLine
    } catch {
        $commandLine = ""
    }
    $looksLikeMedRay =
        $commandLine.Contains($ProjectRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        $commandLine -like "*uvicorn app.main:app*" -or
        $commandLine -like "*vite*--host*127.0.0.1*"

    if ($looksLikeMedRay) {
        Write-Host "Stopping PID $pidValue ($($process.ProcessName))"
        & taskkill.exe /PID $pidValue /T /F | Out-Null
    } else {
        Write-Host "Skipping PID $pidValue ($($process.ProcessName)); it does not look like a MedRay process. Path=$path"
    }
}
