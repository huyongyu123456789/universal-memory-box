@echo off
setlocal
set "INST=%LOCALAPPDATA%\MemoryBox\MemoryBox.bat"
if exist "%INST%" (
  start "Memory Box" "%INST%"
  exit /b 0
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-MemoryBox.ps1"
if errorlevel 1 pause
