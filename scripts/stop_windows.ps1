$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Cache = Join-Path $ProjectRoot "data\cache"
$State = Join-Path $Cache "launcher.json"
if (!(Test-Path -LiteralPath $State)) {
  Write-Host "No MedRay launcher session was found."
  exit 0
}
try {
  $Session = Get-Content -LiteralPath $State -Raw | ConvertFrom-Json
  if ($Session.nonce -notmatch '^[a-f0-9]{32}$') { throw "No current launcher session was found. Close its window or press Ctrl+C." }
  @{ nonce = $Session.nonce } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Cache "launcher-stop.json") -Encoding ASCII
  Write-Host "Stop requested. MedRay will close its own services and release their ports."
} catch {
  Write-Host "Could not stop MedRay: $($_.Exception.Message)"
  exit 1
}
