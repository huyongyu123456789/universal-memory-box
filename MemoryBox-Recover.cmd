@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Please drag a .mbxrecovery file onto this file.
  pause
  exit /b 1
)
echo.
echo Memory Box Disaster Recovery
echo ----------------------------
echo The recovery code will be requested locally and hidden while you type.
echo Do not paste the recovery code into an AI chat.
echo.
if exist "MemoryBox-CLI.exe" (
  "MemoryBox-CLI.exe" recovery-restore "%~1"
) else if exist "runtime\python.exe" (
  "runtime\python.exe" memorybox_main.py recovery-restore "%~1"
) else (
  where py >nul 2>nul && (py -3 memorybox_main.py recovery-restore "%~1") || python memorybox_main.py recovery-restore "%~1"
)
if errorlevel 1 (
  echo.
  echo Memory Box recovery failed. The recovery file was not modified.
  pause
  exit /b 1
)
echo.
echo Device identity restored successfully.
pause
start "" "%~dp0MemoryBox.bat"
endlocal
