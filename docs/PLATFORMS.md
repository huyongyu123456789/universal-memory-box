# Platform release architecture — v0.16

## Windows

- Native desktop shell: pywebview + WebView2.
- Tray: pystray.
- Release: `MemoryBox.exe` + `MemoryBox-CLI.exe`.
- Red cavalry `.ico`.
- Double-click package associations for `.mboxpack`, `.mboxenc`, `.mbxrecovery`.

## macOS

- Native desktop shell: pywebview Cocoa/WebKit backend.
- Release target: `MemoryBox.app` + `MemoryBox-CLI` inside a `.dmg`.
- Red cavalry `.icns`.
- Optional per-user LaunchAgent for login startup.
- Smooth external double-click distribution requires Developer ID signing + notarization; workflow support is included, but credentials belong to the publisher.

## HarmonyOS NEXT

- Native ArkTS/ArkUI Stage-model client under `harmonyos/MemoryBoxHarmony`.
- Uses HarmonyOS `relationalStore` (SQLite-backed RDB) for local data.
- Targets phone/tablet/2-in-1.
- Release HAP/APP signing requires DevEco Studio/AppGallery Connect publisher credentials.
- v0.16 establishes the native local-store/UI foundation; full encrypted transfer interoperability remains explicitly staged rather than falsely claimed as complete.
