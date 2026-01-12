Param(
  [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$py = $null

# Prefer active venv if available.
if ($env:VIRTUAL_ENV) {
  $venvPy = Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe'
  if (Test-Path $venvPy) { $py = $venvPy }
}

if (-not $py) {
  $localVenvPy = Join-Path $Root '.venv\Scripts\python.exe'
  if (Test-Path $localVenvPy) { $py = $localVenvPy }
}

if (-not $py) {
  $parentVenvPy = Join-Path (Split-Path -Parent $Root) '.venv\Scripts\python.exe'
  if (Test-Path $parentVenvPy) { $py = $parentVenvPy }
}

if (-not $py) { $py = 'python' }

Write-Host ("[INFO] Using Python: {0}" -f $py)

# Verify PyInstaller exists
& $py -m PyInstaller --version | Out-Null

# Verify PySide6 exists; otherwise EXE will crash.
& $py -c "import PySide6" | Out-Null

if ($Clean) {
  Write-Host '[INFO] Cleaning build artifacts...'
  if (Test-Path 'build') { Remove-Item -Recurse -Force 'build' }
  if (Test-Path 'dist')  { Remove-Item -Recurse -Force 'dist' }
}

# Common Windows failure: dist\DayzModManager.exe is locked by a running process
# or AV scanner. Try to release the lock before building.
Write-Host '[INFO] Releasing any locked DayzModManager.exe...'
try {
  Get-Process -Name 'DayzModManager' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
} catch {
  # ignore
}

$distExe = Join-Path $Root 'dist\DayzModManager.exe'
if (Test-Path $distExe) {
  try {
    Remove-Item -Force $distExe -ErrorAction Stop
  } catch {
    Write-Host '[ERROR] Cannot delete dist\DayzModManager.exe (it is still locked).' -ForegroundColor Red
    Write-Host '        Close the app, disable antivirus real-time scan for this folder,'
    Write-Host '        or run: .\build.ps1 -Clean' 
    throw
  }
}

Write-Host '[INFO] Building EXE with PyInstaller spec...'
& $py -m PyInstaller --noconfirm --clean 'DayzModManager.spec'

Write-Host '[OK] Build complete.'
Write-Host ("      Output: {0}" -f (Join-Path $Root 'dist\DayzModManager.exe'))
