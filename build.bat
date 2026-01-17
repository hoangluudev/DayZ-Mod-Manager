@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Quick build script for DayzModManager (Windows)
REM Usage:
REM   build.bat                 -> build (prod)
REM   build.bat prod            -> production build (no console, UPX enabled if available)
REM   build.bat dev             -> development build (console enabled, UPX disabled)
REM   build.bat clean           -> delete build/ + dist/ (no build)
REM   build.bat clean prod      -> clean then prod build
REM   build.bat clean dev       -> clean then dev build
REM   build.bat nopause         -> do not pause at the end (can be combined)

cd /d "%~dp0"

set "PF86=%ProgramFiles(x86)%"
set "PF64=%ProgramFiles%"

set "PYEXE="
set "NOPAUSE=0"

set "MODE=prod"
set "MODE_EXPLICIT=0"
set "DO_CLEAN=0"
set "DO_INSTALLER=0"

REM Parse args (order-independent)
:parse_args
if "%~1"=="" goto :args_done
if /I "%~1"=="nopause" (
  set "NOPAUSE=1"
) else if /I "%~1"=="clean" (
  set "DO_CLEAN=1"
) else if /I "%~1"=="installer" (
  set "DO_INSTALLER=1"
) else if /I "%~1"=="prod" (
  set "MODE=prod"
  set "MODE_EXPLICIT=1"
) else if /I "%~1"=="dev" (
  set "MODE=dev"
  set "MODE_EXPLICIT=1"
) else (
  echo [ERROR] Unknown argument: %~1
  echo         Valid: prod ^| dev ^| clean ^| nopause
  goto :fail
)
shift
goto :parse_args

:args_done

REM If installer requested, ensure Inno Setup compiler exists BEFORE doing long build steps.
set "ISCC="
if "%DO_INSTALLER%"=="1" goto :check_inno
goto :after_inno_check

:check_inno
if defined ISCC_PATH if exist "%ISCC_PATH%" set "ISCC=%ISCC_PATH%"
if not defined ISCC if not "%PF86%"=="" if exist "%PF86%\Inno Setup 6\ISCC.exe" set "ISCC=%PF86%\Inno Setup 6\ISCC.exe"
if not defined ISCC if not "%PF64%"=="" if exist "%PF64%\Inno Setup 6\ISCC.exe" set "ISCC=%PF64%\Inno Setup 6\ISCC.exe"
if not defined ISCC goto :inno_missing
goto :after_inno_check

:inno_missing
echo [ERROR] Inno Setup compiler (ISCC.exe) not found.
echo         Install Inno Setup 6, or set env var ISCC_PATH to ISCC.exe
echo         Example: setx ISCC_PATH "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
goto :fail

:after_inno_check

REM Prefer currently activated venv if available.
if defined VIRTUAL_ENV if exist "%VIRTUAL_ENV%\Scripts\python.exe" set "PYEXE=%VIRTUAL_ENV%\Scripts\python.exe"

REM Fallback: parent-folder venv (common workspace layout).
if not defined PYEXE if exist "%CD%\..\.venv\Scripts\python.exe" set "PYEXE=%CD%\..\.venv\Scripts\python.exe"

if exist "%CD%\.venv\Scripts\python.exe" set "PYEXE=%CD%\.venv\Scripts\python.exe"
if not defined PYEXE set "PYEXE=python"

echo [INFO] Using Python: %PYEXE%

if exist "%PYEXE%" goto :py_ok

REM If PYEXE is not a file path, try locating it on PATH.
where /q %PYEXE% 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found on PATH and no .venv detected.
  echo         Create venv: python -m venv .venv
  echo         Then install deps: .venv\Scripts\python -m pip install -r requirements.txt
  goto :fail
)

:py_ok

REM Verify PyInstaller exists in this interpreter.
"%PYEXE%" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] PyInstaller is not installed for: %PYEXE%
  echo         Fix: "%PYEXE%" -m pip install -r requirements.txt
  goto :fail
)

REM Verify PySide6 exists in this interpreter; otherwise the EXE will crash.
"%PYEXE%" -c "import PySide6" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] PySide6 is not installed for: %PYEXE%
  echo         Fix: "%PYEXE%" -m pip install -r requirements.txt
  goto :fail
)

REM Verify Pillow exists (needed to generate a multi-size .ico).
"%PYEXE%" -c "import PIL" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Pillow is not installed for: %PYEXE%
  echo         Fix: "%PYEXE%" -m pip install -r requirements.txt
  goto :fail
)

echo [INFO] Generating app_icon.ico from logo...
"%PYEXE%" tools\generate_icons.py --input assets\icons\new_logo.png --output assets\icons\app_icon.ico
if errorlevel 1 (
  echo [ERROR] Failed to generate app_icon.ico
  goto :fail
)

echo [INFO] Embedding configs\app.json into the executable...
"%PYEXE%" tools\embed_app_config.py
if errorlevel 1 (
  echo [ERROR] Failed to embed app config.
  goto :fail
)

REM Read app version from configs\app.json (used for installer naming).
set "APP_VERSION=0.0.0"
for /f "delims=" %%V in ('"%PYEXE%" tools\print_app_version.py 2^>nul') do set "APP_VERSION=%%V"
if not defined APP_VERSION set "APP_VERSION=0.0.0"
echo [INFO] AppVersion: %APP_VERSION%

if /I "%~1"=="clean" (
  REM legacy path: handled by DO_CLEAN now
)

if "%DO_CLEAN%"=="1" (
  echo [INFO] Cleaning build artifacts...
  if exist build rmdir /s /q build
  if exist dist rmdir /s /q dist
  if "%MODE_EXPLICIT%"=="0" (
    echo [OK] Clean complete.
    if "%NOPAUSE%"=="0" (
      echo.
      pause
    )
    endlocal
    exit /b 0
  )
)

REM Common Windows failure: dist\DayzModManager.exe is locked by a running process.
REM Try to release the lock before building.
echo [INFO] Releasing any locked DayzModManager.exe...
taskkill /im DayzModManager.exe /F >nul 2>nul
if exist "dist\DayzModManager\DayzModManager.exe" del /f /q "dist\DayzModManager\DayzModManager.exe" >nul 2>nul

set "DMM_BUILD_MODE=%MODE%"
echo [INFO] Build mode: %DMM_BUILD_MODE%

echo [INFO] Building EXE with PyInstaller spec...
"%PYEXE%" -m PyInstaller --noconfirm --clean DayzModManager.spec
if errorlevel 1 (
  echo [ERROR] Build failed.
  goto :fail
)

if not "%DO_INSTALLER%"=="1" goto :after_installer
if not exist "installer.iss" (
  echo [ERROR] installer.iss not found. Cannot build installer.
  goto :fail
)

echo [INFO] Compiling installer with Inno Setup...
"%ISCC%" /Qp "/DAppVersion=%APP_VERSION%" "installer.iss"
if errorlevel 1 (
  echo [ERROR] Installer build failed.
  goto :fail
)
echo [OK] Installer compiled.
echo      Output: %CD%\installer_output\DayzModManager_Setup_%APP_VERSION%.exe

:after_installer

echo [OK] Build complete.
echo      Output: %CD%\dist\DayzModManager\DayzModManager.exe
if "%NOPAUSE%"=="0" (
  echo.
  pause
)
endlocal
exit /b 0

:fail
echo.
echo [HINT] If you double-clicked this file, run it from a terminal to see output:
echo        cd /d "%CD%" ^&^& build.bat
echo.
if "%NOPAUSE%"=="0" pause
endlocal
exit /b 1
