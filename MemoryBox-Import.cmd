@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Please drag a .mboxpack or .mboxenc file onto this file.
  pause
  exit /b 1
)
set "MODE=import-pack"
if /I "%~x1"==".mboxenc" set "MODE=import-encrypted"
if exist "MemoryBox-CLI.exe" (
  "MemoryBox-CLI.exe" %MODE% "%~1" --open
) else if exist "runtime\python.exe" (
  "runtime\python.exe" memorybox_main.py %MODE% "%~1" --open
) else (
  where py >nul 2>nul && (py -3 memorybox_main.py %MODE% "%~1" --open) || python memorybox_main.py %MODE% "%~1" --open
)
if errorlevel 1 (
  echo.
  echo Memory Box import failed. The source package was not modified.
  pause
  exit /b 1
)
start "" "%~dp0MemoryBox.bat"
endlocal
