# Memory Box v0.14 Multi-platform Apps

## Product goal

One product identity and one memory format across Windows, macOS and HarmonyOS, with native launch behavior on each platform. The red cavalry artwork is the master icon in `assets/icons/master.png`.

## Windows

- Artifact: `MemoryBox.exe` + `MemoryBox-CLI.exe`.
- Renderer: pywebview with WebView2.
- Launch: double-click `MemoryBox.exe`; no console window.
- File open: `.mboxpack` and `.mboxenc` prefer the native EXE; recovery remains human-gated.
- Icon: `assets/icons/windows/MemoryBox.ico`.

## macOS

- Artifacts: `Memory Box.app`, architecture-specific ZIP, and DMG.
- Renderer: pywebview uses the native Cocoa/WKWebView backend on macOS.
- Architectures: Apple Silicon arm64 and Intel x86_64 are built separately in GitHub Actions.
- Launch: double-click `Memory Box.app`. `--argv-emulation` plus `CFBundleDocumentTypes` forwards Finder document-open events for `.mboxpack`, `.mboxenc`, and `.mbxrecovery`.
- Start at login: user LaunchAgent at `~/Library/LaunchAgents/com.memorybox.desktop.plist`.
- Icon: standard macOS IconSet converted to `.icns` during the macOS build.
- Signing: CI performs ad-hoc signing to verify bundle integrity. Public frictionless distribution requires a real Developer ID signature and Apple notarization.

## HarmonyOS

- Project: `platforms/harmonyos`.
- Model: Stage/ArkTS, target API 26.0.0.
- Devices: phone, tablet, 2in1.
- Launch: `EntryAbility` is singleton and declares `ohos.want.action.home` + `entity.system.home`; tapping the launcher icon opens the main page.
- Current v0.14 scope: native quick-save, local persistent memory IDs, search/list, responsive ArkUI shell and shared branding. This is intentionally described as a HarmonyOS companion/core build rather than claiming full parity with the desktop Python E2EE/MCP stack.
- Build: DevEco Studio 6.1+ / API 26.0.0. A release HAP/APP needs a valid signing profile.

## UX optimization

- Shared low-noise design: generous spacing, rounded surfaces, restrained shadows, neutral backgrounds, red brand accent.
- Desktop keeps high-information workflows while mobile prioritizes quick save and recall.
- Human-only recovery secrets remain outside Agent/MCP surfaces.
- Platform-native launch semantics are preferred over browser URLs or terminal commands.
