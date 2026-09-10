@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Register-Transfer-Association.ps1"
if errorlevel 1 pause
