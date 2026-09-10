# Memory Box v0.14.0 Release Status

## Completed in this source release

- Unified red cavalry branding for Windows, macOS, and HarmonyOS.
- Windows native PyInstaller configuration for `MemoryBox.exe` and `MemoryBox-CLI.exe`.
- Windows `.mboxpack` / `.mboxenc` native-open association prefers `MemoryBox.exe`.
- Windows bootstrap copies icon assets and uses the branded icon for the Start Menu shortcut.
- macOS native `.app`/`.dmg` GitHub Actions workflow for Apple Silicon and Intel.
- macOS Finder document associations and LaunchAgent start-at-login support.
- HarmonyOS API 26 Stage/ArkTS project with launcher `EntryAbility`, local quick-save/search/list, and red cavalry icon.
- Shared desktop UI now uses a restrained red brand accent with Light / Dark / Auto themes.
- 75/75 regression tests pass under strict `ResourceWarning` handling.
- Fresh-wheel CLI/desktop-entry smoke test passes in an isolated environment.

## Platform-native build boundary

This Linux build environment cannot produce or runtime-test a Windows WebView2 EXE, a macOS `.app`/`.dmg`, or a signed HarmonyOS HAP/APP. The repository contains the platform build definitions and validation contracts, but platform-native binaries must be produced on their native toolchains:

- Windows: GitHub Actions `windows-latest` -> `MemoryBox.exe` + `MemoryBox-CLI.exe`.
- macOS: GitHub Actions macOS runners -> `Memory Box.app` + `.dmg` for arm64/x86_64.
- HarmonyOS: DevEco Studio/HarmonyOS SDK with a valid signing profile -> signed HAP/APP.

## Launch contract

- Windows: double-click `MemoryBox.exe`.
- macOS: double-click `Memory Box.app`.
- HarmonyOS: tap the installed Memory Box launcher icon.

macOS distribution to arbitrary Macs without first-launch security prompts requires Developer ID signing and notarization. HarmonyOS device installation requires a valid signing configuration.
