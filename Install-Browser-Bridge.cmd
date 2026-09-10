@echo off
setlocal
set "ROOT=%~dp0"
set "EXT=%ROOT%integrations\browser-extension"
if not exist "%EXT%\manifest.json" (
  echo Browser Bridge extension not found: %EXT%
  pause
  exit /b 1
)
start "" explorer.exe "%EXT%"
where chrome.exe >nul 2>nul
if %errorlevel%==0 (
  start "" chrome.exe "chrome://extensions/"
  goto :done
)
where msedge.exe >nul 2>nul
if %errorlevel%==0 (
  start "" msedge.exe "edge://extensions/"
  goto :done
)
start "" "chrome://extensions/"
:done
echo.
echo 1. Turn on Developer mode in Chrome/Edge extensions.
echo 2. Click "Load unpacked" / "加载已解压的扩展程序".
echo 3. Choose: %EXT%
echo.
echo The browser requires this final confirmation; Memory Box will not bypass it.
pause
