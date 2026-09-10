# Memory Box v0.13 Windows Desktop Shell

Memory Box v0.13 wraps the local v0.12 control-center UI in a native Windows window while keeping the existing local-first HTTP/MCP architecture.

## Runtime architecture

```text
MemoryBox.exe (windowed, pywebview/WebView2)
  ├─ native window + drag/drop
  ├─ system tray + notifications
  └─ 127.0.0.1 ephemeral local HTTP server
       └─ existing Memory Box APIs / SQLite / sync / insurance

MemoryBox-CLI.exe (console)
  ├─ MCP stdio
  ├─ import/export
  ├─ recovery helper
  └─ automation/scheduled-task commands
```

The desktop shell does not replace the browser UI or MCP server. It embeds the same local UI in a native window, so there is one functional surface rather than a separate desktop-only mock.

## Desktop behavior

- Closing the main window minimizes to the system tray by default.
- The tray menu provides Open, Sync now, Run insurance, and Quit.
- The Settings page can toggle minimize-to-tray, Windows login startup, and system notifications.
- `.mboxpack` and `.mboxenc` can open through the desktop app. `.mbxrecovery` keeps the separate local recovery helper so the recovery code is requested outside AI/MCP contexts.
- Supported Memory Box package files can be dragged into the native window; the pywebview desktop bridge receives the full local file path and imports through the same validated import pipeline.

## Security boundaries

- UI/backend traffic stays on `127.0.0.1`.
- Recovery codes are not exposed through the desktop JS bridge or MCP.
- Startup registration uses the current-user Windows Run key only when the user enables it.
- File drag/drop reuses the existing package validation/checksum/decryption code; it does not execute dropped files.

## Windows build

GitHub Actions builds two executables:

- `MemoryBox.exe`: PyInstaller `--windowed`, pywebview WebView2 shell.
- `MemoryBox-CLI.exe`: PyInstaller `--console`, used by MCP and local maintenance helpers.

This split avoids a console window for normal users while preserving reliable stdio for MCP.

## Source/bootstrap fallback

If pywebview/pystray are unavailable, `memorybox desktop` falls back to the existing localhost browser UI rather than failing to open the memory database.
