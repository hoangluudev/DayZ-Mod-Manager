@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Quick build script for DayzModManager (Windows)
REM Usage:
REM   build.bat           -> build using spec
REM   build.bat clean     -> delete build/ + dist/ then build
REM   build.bat nopause   -> do not pause at the end

cd /d "%~dp0"

set "PYEXE="
set "NOPAUSE=0"

if /I "%~1"=="nopause" set "NOPAUSE=1"
if /I "%~2"=="nopause" set "NOPAUSE=1"

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

if /I "%~1"=="clean" (
  echo [INFO] Cleaning build artifacts...
  if exist build rmdir /s /q build
  if exist dist rmdir /s /q dist
)

echo [INFO] Building EXE with PyInstaller spec...
"%PYEXE%" -m PyInstaller --noconfirm --clean DayzModManager.spec
if errorlevel 1 (
  echo [ERROR] Build failed.
  goto :fail
)

echo [OK] Build complete.
echo      Output: %CD%\dist\DayzModManager.exe
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
