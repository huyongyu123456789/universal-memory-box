@echo off
setlocal
cd /d "%~dp0"
if not "%~1"=="" (
  if exist "MemoryBox.exe" (
    start "Memory Box" "MemoryBox.exe" "%~1"
    exit /b 0
  )
  call "%~dp0MemoryBox-Import.cmd" "%~1"
  exit /b %errorlevel%
)
if exist "MemoryBox.exe" (
  start "Memory Box" "MemoryBox.exe"
  exit /b 0
)
if exist "runtime\pythonw.exe" (
  start "Memory Box" "runtime\pythonw.exe" memorybox_main.py desktop
  exit /b 0
)
where pyw >nul 2>nul && (start "Memory Box" pyw memorybox_main.py desktop & exit /b 0)
where pythonw >nul 2>nul && (start "Memory Box" pythonw memorybox_main.py desktop & exit /b 0)
echo Memory Box desktop runtime not found. Please run Start-MemoryBox.cmd or Install-MemoryBox.cmd first.
pause
