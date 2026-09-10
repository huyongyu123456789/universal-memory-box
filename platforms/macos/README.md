# Memory Box for macOS

The macOS desktop build uses the same local-first Python core and v0.12+ UI as Windows, wrapped in pywebview's native Cocoa/WKWebView backend.

## User experience

- Double-click **Memory Box.app** to open the app.
- `.mboxpack` and `.mboxenc` files can be opened with Memory Box from Finder.
- `.mbxrecovery` routes to the Recovery screen and still requires the recovery code locally.
- Optional start-at-login uses `~/Library/LaunchAgents/com.memorybox.desktop.plist`.
- Closing the main window can keep Memory Box in the menu-bar/tray when enabled.

## Build

Use the GitHub Actions workflow `build-macos.yml`, or on a Mac:

```bash
python3 -m pip install --upgrade pip pyinstaller ".[desktop,macos]"
iconutil -c icns assets/icons/macos/MemoryBox.iconset -o assets/icons/macos/MemoryBox.icns
pyinstaller --noconfirm --clean --onedir --windowed --argv-emulation \
  --name "Memory Box" \
  --icon assets/icons/macos/MemoryBox.icns \
  --osx-bundle-identifier com.memorybox.desktop \
  --add-data "assets/icons/master.png:assets/icons" \
  memorybox_desktop.py
python3 platforms/macos/postprocess_plist.py "dist/Memory Box.app/Contents/Info.plist"
codesign --deep --force --sign - "dist/Memory Box.app"
```

For frictionless double-click launch on other users' Macs, release builds should be signed with an Apple Developer ID certificate and notarized. Ad-hoc signing verifies bundle integrity but does not replace Developer ID notarization.
