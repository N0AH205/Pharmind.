@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-pharmind-local.ps1"
if errorlevel 1 (
  echo.
  echo Pharmind Local could not start. Follow the message above, then double-click this file again.
  pause
)
endlocal
