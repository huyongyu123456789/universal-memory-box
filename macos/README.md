# Memory Box for macOS

v0.16 uses the same local SQLite/MCP core as Windows and runs the desktop UI through pywebview's native macOS Cocoa/WebKit backend. The macOS release workflow builds a `MemoryBox.app`, packages it in a `.dmg`, bundles the red cavalry icon and the optional local BGE semantic model cache, and includes `MemoryBox-CLI` for MCP/automation workflows.

For frictionless double-click launch on downloaded Macs, use a Developer ID Application certificate and Apple notarization. The GitHub workflow supports signing/notarization when the required repository secrets are configured. Without those credentials, CI produces an ad-hoc signed development DMG which macOS Gatekeeper may require the user to explicitly approve once.

The desktop settings layer supports a per-user LaunchAgent (`~/Library/LaunchAgents/com.memorybox.desktop.plist`) for optional start-at-login; it does not require administrator privileges.
