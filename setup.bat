@echo off
setlocal
cd /d "%~dp0"
title Kitchen Sink - Setup

echo.
echo   ==========================================
echo    Kitchen Sink - first-time setup
echo   ==========================================
echo.

rem The Windows Store ships a fake "python.exe" that only opens the Store page,
rem so each candidate is tested by actually running it.
set "PYEXE="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PYEXE=py -3"

if not defined PYEXE (
  python --version >nul 2>&1
  if not errorlevel 1 set "PYEXE=python"
)

if not defined PYEXE (
  echo   Python 3 was not found.
  echo.
  echo   Install it from https://www.python.org/downloads/windows/
  echo   and tick "Add python.exe to PATH" at the bottom of the installer.
  echo.
  echo   If Windows opens the Microsoft Store when you type "python", that is
  echo   a placeholder, not Python. Turn it off under
  echo   Settings ^> Apps ^> Advanced app settings ^> App execution aliases.
  echo.
  pause
  exit /b 1
)

echo   Using: %PYEXE%
%PYEXE% --version

if not exist ".venv\Scripts\python.exe" (
  echo   [1/4] Creating a private Python environment in .venv ...
  %PYEXE% -m venv .venv || goto :fail
) else (
  echo   [1/4] Reusing the existing .venv ...
)

echo   [2/4] Upgrading pip ...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet || goto :fail

echo   [3/4] Installing pywebview, yt-dlp and scdl ...
echo         ^(needs internet — one-time download^)
".venv\Scripts\python.exe" -m pip install -r "src\requirements.txt" || goto :fail

echo   [4/4] Fetching ffmpeg into .\bin ...
rem The app package lives under src\, so run the module from in there.
pushd "src"
"..\.venv\Scripts\python.exe" -m app.ffmpeg_setup
popd

echo.
echo   Done. Launch the app with "Kitchen Sink.bat".
echo.
pause
exit /b 0

:fail
echo.
echo   Setup failed. Scroll up for the error.
echo.
pause
exit /b 1
