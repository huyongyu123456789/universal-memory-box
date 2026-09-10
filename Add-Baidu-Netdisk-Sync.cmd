@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Add-Baidu-Netdisk-Sync.ps1"
if errorlevel 1 pause
