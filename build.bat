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

set "PYEXE="
set "NOPAUSE=0"

set "MODE=prod"
set "MODE_EXPLICIT=0"
set "DO_CLEAN=0"

REM Parse args (order-independent)
:parse_args
if "%~1"=="" goto :args_done
if /I "%~1"=="nopause" (
  set "NOPAUSE=1"
) else if /I "%~1"=="clean" (
  set "DO_CLEAN=1"
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
if exist "dist\DayzModManager.exe" del /f /q "dist\DayzModManager.exe" >nul 2>nul

set "DMM_BUILD_MODE=%MODE%"
echo [INFO] Build mode: %DMM_BUILD_MODE%

echo [INFO] Building EXE with PyInstaller spec...
"%PYEXE%" -m PyInstaller --noconfirm --clean DayzModManager.spec
if errorlevel 1 (
  echo [ERROR] Build failed.
  goto :fail
)

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
pause
endlocal
exit /b 1
