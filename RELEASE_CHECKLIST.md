# Memory Box v0.14.0 Release Checklist

- [x] Python package and Browser/Kimi/WorkBuddy metadata synchronized to 0.14.0.
- [x] Native desktop module wraps the live v0.12 control-center APIs rather than a static mock.
- [x] Desktop settings: minimize-to-tray, notifications and Windows login startup.
- [x] System tray menu: Open, Sync now, Run insurance, Quit.
- [x] Native package drag/drop routes through validated `.mboxpack` / `.mboxenc` import logic.
- [x] `.mbxrecovery` remains human-only and does not auto-consume recovery secrets.
- [x] Embedded local server gained clean start/stop lifecycle for the desktop process.
- [x] Windows build workflow creates `MemoryBox.exe` (`--windowed`) and `MemoryBox-CLI.exe` (`--console`).
- [x] MCP/import/recovery/insurance command helpers prefer `MemoryBox-CLI.exe`.
- [x] Bootstrap installer installs private pywebview/pystray/Pillow runtime without modifying system Python.
- [x] Browser mode remains available as a safe fallback when desktop extras are unavailable.
- [x] SQLite schema remains v8; no data migration is required from v0.12.
- [x] 71/71 source regression tests pass under `ResourceWarning` strict mode.
- [x] Fresh-wheel install smoke test passes: install -> save -> list -> desktop entrypoint help -> embedded server/UI health.
- [ ] Run GitHub Actions on `windows-latest` and attach the resulting native `MemoryBox.exe` + `MemoryBox-CLI.exe` release ZIP.
