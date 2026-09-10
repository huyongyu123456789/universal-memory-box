@echo off
setlocal
set "INST=%LOCALAPPDATA%\MemoryBox"
set "PY=%INST%\runtime\python.exe"
set "MAIN=%INST%\memorybox_main.py"
if exist "%INST%\MemoryBox-CLI.exe" (
  "%INST%\MemoryBox-CLI.exe" insurance-run
  exit /b %errorlevel%
)
if exist "%PY%" if exist "%MAIN%" (
  "%PY%" "%MAIN%" insurance-run
  exit /b %errorlevel%
)
echo Memory Box is not installed in %%LOCALAPPDATA%%\MemoryBox.
exit /b 2
