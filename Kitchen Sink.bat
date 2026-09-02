@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
  echo Kitchen Sink isn't set up yet - running setup.bat first.
  echo.
  call "setup.bat"
)

if not exist ".venv\Scripts\pythonw.exe" (
  echo.
  echo   Setup did not finish, so there is nothing to launch yet.
  echo   Scroll up for the reason, fix it, then run setup.bat again.
  echo.
  pause
  exit /b 1
)

rem Confirm the environment actually imports before launching windowless,
rem otherwise a broken install just vanishes with no message at all.
".venv\Scripts\python.exe" -c "import webview" >nul 2>&1
if errorlevel 1 (
  echo.
  echo   The Python environment is incomplete ^(pywebview is missing^).
  echo   Run setup.bat again to repair it.
  echo.
  pause
  exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "src\KitchenSink.pyw"
