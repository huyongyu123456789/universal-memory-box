@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Enable-Auto-Insurance.ps1"
if errorlevel 1 pause
