@echo off
cd /d "%~dp0"
title Kitchen Sink - Update

echo.
echo   Updating yt-dlp and scdl. Do this whenever a download starts failing -
echo   YouTube changes things often and yt-dlp ships fixes within days.
echo.

if not exist ".venv\Scripts\python.exe" (
  echo   No .venv found. Run setup.bat first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade yt-dlp
".venv\Scripts\python.exe" -m pip install --upgrade scdl

echo.
echo   Up to date.
echo.
pause
