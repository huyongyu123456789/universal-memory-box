@echo off
setlocal
set "ROOT=%~dp0"
if exist "%ROOT%MemoryBox-CLI.exe" (
  "%ROOT%MemoryBox-CLI.exe" model-install
) else if exist "%LOCALAPPDATA%\MemoryBox\runtime\python.exe" (
  "%LOCALAPPDATA%\MemoryBox\runtime\python.exe" "%LOCALAPPDATA%\MemoryBox\memorybox_main.py" model-install
) else (
  python "%ROOT%memorybox_main.py" model-install
)
pause
