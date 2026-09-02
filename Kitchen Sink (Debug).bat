@echo off
cd /d "%~dp0"
title Kitchen Sink - Debug

echo.
echo   Running Kitchen Sink with the console attached.
echo   Errors appear here instead of disappearing. Close this window to quit.
echo.

if not exist ".venv\Scripts\python.exe" (
  echo   No .venv yet - run setup.bat first.
  echo.
  pause
  exit /b 1
)

set "KITCHEN_SINK_DEBUG=1"
".venv\Scripts\python.exe" "KitchenSink.pyw"

echo.
echo   Kitchen Sink exited with code %errorlevel%.
echo.
pause
