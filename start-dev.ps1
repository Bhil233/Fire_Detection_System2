param(
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSCommandPath
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"

if (-not (Test-Path -LiteralPath $backendDir)) {
  throw "Backend directory not found: $backendDir"
}

if (-not (Test-Path -LiteralPath $frontendDir)) {
  throw "Frontend directory not found: $frontendDir"
}

function Ensure-EnvFile {
  param(
    [Parameter(Mandatory = $true)]
    [string]$DirectoryPath
  )

  $envPath = Join-Path $DirectoryPath ".env"
  $examplePath = Join-Path $DirectoryPath ".env.example"

  if ((-not (Test-Path -LiteralPath $envPath)) -and (Test-Path -LiteralPath $examplePath)) {
    Copy-Item -LiteralPath $examplePath -Destination $envPath
    Write-Host "[setup] Created $envPath from .env.example"
  }
}

Ensure-EnvFile -DirectoryPath $backendDir
Ensure-EnvFile -DirectoryPath $frontendDir

$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $backendPython) {
  $backendRunCommand = "& `"$backendPython`" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
} else {
  $backendRunCommand = "uvicorn main:app --reload --host 0.0.0.0 --port 8000"
  Write-Host "[warn] backend/.venv not found, fallback to global uvicorn."
}

$frontendNodeModules = Join-Path $frontendDir "node_modules"
if (-not (Test-Path -LiteralPath $frontendNodeModules)) {
  Write-Host "[setup] Installing frontend dependencies..."
  & npm install --prefix $frontendDir
}

$backendWindowCommand = "Set-Location -LiteralPath `"$backendDir`"; $backendRunCommand"
$frontendWindowCommand = "Set-Location -LiteralPath `"$frontendDir`"; npm run dev"

if ($DryRun) {
  Write-Host "[dry-run] Backend command:"
  Write-Host $backendWindowCommand
  Write-Host "[dry-run] Frontend command:"
  Write-Host $frontendWindowCommand
  exit 0
}

Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $backendWindowCommand | Out-Null
Start-Sleep -Milliseconds 300
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $frontendWindowCommand | Out-Null

Write-Host ""
Write-Host "Services are starting in two new terminal windows."
Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host "Frontend: http://127.0.0.1:5173"
Write-Host "Stop them by closing the spawned PowerShell windows."
