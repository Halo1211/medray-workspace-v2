param([switch]$WithOptional)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Find-Python {
  $candidates = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
  )
  foreach ($p in $candidates) {
    if (Test-Path $p) {
      try {
        & $p --version *> $null
        if ($LASTEXITCODE -eq 0) { return $p }
      } catch {
        Write-Host "Skipping an unavailable Python candidate: $p"
      }
    }
  }
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) {
    try {
      & $cmd.Source --version *> $null
      if ($LASTEXITCODE -eq 0) { return $cmd.Source }
    } catch {
      Write-Host "Skipping the Python executable found on PATH because it could not run."
    }
  }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { return "py" }
  throw "Python 3.10+ was not found. Install Python from https://www.python.org/downloads/ and run this script again."
}

$Python = Find-Python
Write-Host "Python: $Python"
& $Python --version

if (!(Test-Path ".env")) { Copy-Item ".env.example" ".env" }
if (!(Test-Path ".venv")) { & $Python -m venv .venv }
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r backend\requirements.txt
if ($WithOptional -or $env:MEDRAY_INSTALL_OPTIONAL -eq "1") {
  Write-Host "Installing optional model dependencies..."
  & $VenvPython -m pip install -r backend\requirements-optional.txt
}

$Node = Get-Command node -ErrorAction SilentlyContinue
if (!$Node) { throw "Node.js was not found. Install Node.js LTS and run this script again." }
node --version
npm --version
$NpmCache = Join-Path $Root "data\cache\npm"
New-Item -ItemType Directory -Force -Path $NpmCache | Out-Null
$env:npm_config_cache = $NpmCache
Push-Location frontend
npm install
Pop-Location

$Ollama = Get-Command ollama -ErrorAction SilentlyContinue
if ($Ollama) { Write-Host "Ollama found: $($Ollama.Source)" } else { Write-Host "Ollama is not installed; the built-in mode remains available." }

Write-Host "Setup complete. Run .\start_medray_v2.bat"
