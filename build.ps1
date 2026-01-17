Param(
  [switch]$Clean,
  [switch]$Installer
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

# Ensure we can generate a multi-size Windows .ico
try {
  & $py -c "import PIL" | Out-Null
} catch {
  Write-Host '[INFO] Installing Pillow (for ICO generation)...'
  & $py -m pip install Pillow | Out-Null
}

Write-Host '[INFO] Generating app_icon.ico from logo...'
& $py (Join-Path $Root 'tools\generate_icons.py') --input (Join-Path $Root 'assets\icons\new_logo.png') --output (Join-Path $Root 'assets\icons\app_icon.ico')

Write-Host '[INFO] Embedding configs\app.json into the executable...'
& $py (Join-Path $Root 'tools\embed_app_config.py')

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

$distExe = Join-Path $Root 'dist\DayzModManager\DayzModManager.exe'
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
Write-Host ("      Output: {0}" -f (Join-Path $Root 'dist\DayzModManager\DayzModManager.exe'))

if ($Installer) {
  $iss = Join-Path $Root 'installer.iss'
  if (-not (Test-Path $iss)) {
    Write-Host '[WARN] installer.iss not found. Skipping installer build.'
    return
  }

  $isccCandidates = @()
  if ($env:ISCC_PATH) { $isccCandidates += $env:ISCC_PATH }
  if ($env:ProgramFiles -and (Test-Path (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'))) {
    $isccCandidates += (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
  }
  if ($env:'ProgramFiles(x86)' -and (Test-Path (Join-Path $env:'ProgramFiles(x86)' 'Inno Setup 6\ISCC.exe'))) {
    $isccCandidates += (Join-Path $env:'ProgramFiles(x86)' 'Inno Setup 6\ISCC.exe')
  }

  $iscc = $isccCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
  if (-not $iscc) {
    Write-Host '[WARN] Inno Setup compiler (ISCC.exe) not found. Set ISCC_PATH or install Inno Setup 6.'
    return
  }

  $appJson = Join-Path $Root 'configs\app.json'
  $appVersion = '0.0.0'
  try {
    $cfg = Get-Content -Raw -Path $appJson -Encoding UTF8 | ConvertFrom-Json
    if ($cfg.version) { $appVersion = [string]$cfg.version }
  } catch {
    # ignore and keep default
  }

  Write-Host '[INFO] Compiling installer with Inno Setup...'
  & $iscc /Qp ("/DAppVersion=$appVersion") $iss

  Write-Host '[OK] Installer compiled.'
  Write-Host ("      Output: {0}" -f (Join-Path $Root ("installer_output\\DayzModManager_Setup_{0}.exe" -f $appVersion)))
}
