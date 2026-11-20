@echo off
setlocal
cd /d "%~dp0"
if not exist .env if not defined DATABASE_URL (
  AgroTrack.exe --setup
  if errorlevel 1 (
    pause
    exit /b 1
  )
)
AgroTrack.exe --open-browser
if errorlevel 1 (
  pause
  exit /b 1
)
