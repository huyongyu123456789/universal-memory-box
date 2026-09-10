@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Disable-Auto-Insurance.ps1"
if errorlevel 1 pause
