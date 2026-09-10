@echo off
setlocal
cd /d "%~dp0"
if exist "MemoryBox-CLI.exe" (
  "MemoryBox-CLI.exe" mcp
  exit /b %errorlevel%
)
if exist "runtime\python.exe" (
  "runtime\python.exe" memorybox_main.py mcp
  exit /b %errorlevel%
)
where py >nul 2>nul && (py -3 memorybox_main.py mcp & exit /b %errorlevel%)
python memorybox_main.py mcp
