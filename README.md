# Memory Box

**Local-first SQLite memory and an MCP bridge for AI agents.**

Memory Box stores durable conversation/task context on the user's own machine and exposes it through MCP, CLI, and a local UI. Save once, then recall or resume from Kimi Code, WorkBuddy, Cursor, Gemini CLI, Claude Code, Codex CLI, or any MCP-capable agent.



## v0.14 Cross-platform apps: Windows, macOS and HarmonyOS

v0.14 unifies Memory Box across three user-facing platforms with the same **red cavalry** brand icon. Windows keeps the native `MemoryBox.exe` shell; macOS adds a native `Memory Box.app` built on Cocoa/WKWebView for both Apple Silicon and Intel; HarmonyOS adds an API 26 Stage/ArkTS companion for phone, tablet and 2-in-1 devices.

Launch behavior is explicit: double-click `MemoryBox.exe` on Windows, double-click `Memory Box.app` on macOS, and tap the Memory Box icon on HarmonyOS. Windows/macOS package associations route `.mboxpack` and `.mboxenc` into the existing verified import path; recovery packages remain human-gated. macOS release builds include `.app` and `.dmg` artifacts. HarmonyOS declares a singleton `EntryAbility` with the system home action/entity so tapping the launcher icon enters the app directly. See `docs/MULTIPLATFORM.md`.

> macOS distribution note: a locally/ad-hoc signed `.app` has a valid launch bundle, but truly frictionless first-launch on arbitrary Macs requires Apple Developer ID signing and notarization. HarmonyOS likewise requires a valid DevEco/AppGallery signing profile before installing a release HAP/APP on devices.


## v0.13 Native Windows Desktop Shell

v0.13 turns the v0.12 control center into a real Windows desktop application shell. `MemoryBox.exe` uses pywebview/WebView2 for the native window and pystray for the system tray, while the existing local API continues to run only on `127.0.0.1`. Closing/minimizing can send Memory Box to the tray; the tray provides Open, Sync now, Run insurance and Quit. The Settings page exposes minimize-to-tray, Windows login startup and notifications only when running inside the native desktop shell.

Windows release builds are intentionally split into `MemoryBox.exe` (windowed desktop UI) and `MemoryBox-CLI.exe` (console/MCP/import/recovery commands) so normal use has no black console window while MCP keeps reliable stdio. Native drag/drop of `.mboxpack`/`.mboxenc` reuses the validated import pipeline. `.mbxrecovery` remains on the separate local recovery helper so recovery codes are never exposed to the desktop JS bridge or AI agents. See `docs/DESKTOP.md`.

## v0.12 Desktop Control Center

v0.12 redesigns the local UI into a calm desktop control center with an Apple-inspired visual language (not an Apple UI clone): generous whitespace, translucent chrome, rounded surfaces, thin separators, restrained shadows and one primary accent. Home now surfaces recovery health, recent memories, quick resume/save/transfer actions, E2EE endpoints and insurance status. Memories, Agents, Sync, Insurance, Recovery and Transfer share the same responsive shell.

The UI supports **Light / Dark / Auto** appearance and remains local-first: the normal server still binds to `127.0.0.1`, uses no remote fonts/analytics, and human-only recovery secrets remain outside MCP. See `docs/UI.md`.

## v0.11 Automatic Insurance and Disaster-Readiness Self-Test

Memory Box can now create periodic **full-library E2EE insurance snapshots** containing memories, versions, metadata, and managed attachments. Configure an E2EE Baidu Netdisk/OneDrive/NAS/sync-folder endpoint, then enable automatic insurance from the local UI or CLI. A GREEN/YELLOW/RED self-test checks SQLite integrity, attachment availability, encrypted snapshot freshness, recovery-vault availability, and recovery-code drill history.

```bash
memorybox insurance-configure <endpoint-id> --interval-hours 24 --retention 7 --deep-verify
memorybox insurance-run --force
memorybox insurance-health --deep
memorybox recovery-verify MemoryBox-Recovery.mbxrecovery
```

The recovery code remains local-only and is never exposed through MCP. Windows users may opt into an hourly Task Scheduler wake-up with `Enable-Auto-Insurance.cmd`; it is not enabled silently. See `docs/INSURANCE.md`.


## Features

- One-call conversation save with automatic title/category fallback
- Stable IDs (`M000001`), categories and tags
- SQLite FTS5 search with LIKE fallback
- Pin, favorite, archive, append with version history
- Related-memory lookup, merge, and multi-memory Resume Context
- Import from Universal Agent Memory v0.3 JSON vaults
- Local MCP stdio server with agent-facing memory tools
- Local web UI bound to `127.0.0.1`
- Agent scanner and connector helpers
- WorkBuddy MCP + Skill connector bundle

## GitHub one-click release

On Windows, double-click `Publish-To-GitHub.cmd` from the extracted source folder to push `main` and the `v0.14.0` tag to the configured repository. The tag triggers Windows and macOS release builds; main also triggers CI and HarmonyOS validation. See `docs/GITHUB_RELEASE.md`.

## Quick start

Windows: extract the release and double-click `Install-MemoryBox.cmd`. The bootstrap installs into `%LOCALAPPDATA%\MemoryBox`, downloads an isolated Python runtime on first install, creates a Start Menu shortcut, opens the local UI, and performs a one-time auto-link scan for detected local MCP agents. Set `MEMORYBOX_NO_AUTOLINK=1` to disable auto-linking.

Source desktop mode:

```bash
python memorybox_main.py desktop
```

Browser-only fallback:

```bash
python memorybox_main.py app
```

MCP stdio:

```bash
python memorybox_main.py mcp
```

## Natural-language workflow

Once the agent is connected through MCP, users can say:

- “Save this conversation to Memory Box.”
- “Show my manuscript memories.”
- “Open M000007.”
- “Append this to M000007.”
- “Resume M000007 and continue the previous task.”
- “Retrieve all memories related to project X and continue.”

## Supported integration paths

Kimi Code/Kimi CLI, Cursor and Gemini CLI use standard MCP config files. Tencent CodeBuddy and Qoder/Qoder CN are also supported through their MCP CLIs when detected. Claude Code and Codex CLI can be configured via their MCP CLIs when detected. WorkBuddy uses the bundled `integrations/workbuddy` MCP + Skill connector. Generic clients can point to the local stdio MCP command.

ChatGPT has a platform limitation: it cannot directly reach a localhost MCP server. A supported remote MCP path such as Secure MCP Tunnel/custom apps is required for direct ChatGPT connectivity; otherwise export a Resume Context. Memory Box does not claim to bypass that restriction.

## Privacy

No cloud account, no telemetry, no automatic upload. The database lives locally (`%LOCALAPPDATA%\MemoryBox\memorybox.db` on Windows or `~/.memorybox/memorybox.db` elsewhere).

## MCP tools

`memory_save`, `memory_list`, `memory_get`, `memory_append`, `memory_categories`, `memory_resume`, `memory_related`, `memory_bundle`, `memory_merge`, `memory_pin`, `memory_favorite`, `memory_device_identity`, `memory_sync_add_folder`, `memory_sync_endpoints`, `memory_sync_detect`, `memory_sync_devices`, `memory_sync_trust_device`, `memory_sync_untrust_device`, `memory_sync_security`, `memory_sync_set_encryption`, `memory_sync_send`, `memory_sync_pull`, `memory_lan_pair`, `memory_lan_discover`, `memory_lan_send_pack`.

## Tests

```bash
python -m unittest discover -s tests -v
```

MIT License.


## Browser Bridge v0.14

The included Chrome/Edge Manifest V3 extension bridges web-only AI chats to the local Memory Box. It can save selected text, capture the current visible conversation, let the user pick local attachment files, search local memories, copy a Resume Context, and inject that context into the active chat composer without automatically sending it. Browser-saved memories include the source agent and source URL. Existing databases migrate in-place to schema v8.

Run `Install-Browser-Bridge.cmd` on Windows to open the extension folder and the browser extension manager. The browser requires the user to confirm loading an unpacked extension.


## Complete session capsules (v0.7)

Export selected memories, a category/search result, or the entire vault to a single `.mboxpack` file or a portable transfer folder. Packages contain `manifest.json`, `memories.json`, `resume.md`, `viewer.html`, and `README.txt`. They are data-only ZIP-compatible packages; import reads only these known files and validates SHA-256 checksums.

```bash
memorybox export-pack MemoryBox-All.mboxpack
memorybox export-pack CRAB.mboxpack --query CRAB
memorybox export-pack TransferFolder --folder
memorybox inspect-pack MemoryBox-All.mboxpack
memorybox import-pack MemoryBox-All.mboxpack --open
```

Each Memory Box installation has a stable device ID. Imports are tracked by `(source_device_id, origin_memory_id)`, so re-imports are idempotent and an ID collision on another computer is remapped instead of overwriting local memory. `viewer.html` provides an offline replay view even without Memory Box. Windows installs associate `.mboxpack` with the safe importer for double-click import.

Complete-session packages are **not encrypted** in v0.7; treat them as private documents. Linked files are content-addressed by SHA-256 and absolute source paths are not exported. See `docs/TRANSFER.md` and `docs/ATTACHMENTS.md`.


## Complete-session attachments (v0.7)

Attach real PDFs, Word files, images, CSVs, code and logs to a memory with `memorybox attach` or the `memory_attach_file` MCP tool. Files are copied into a local SHA-256-addressed store and deduplicated. `session-pack` / `export-pack` automatically carries linked files inside transfer-format-v2 `.mboxpack` capsules. Import restores the bytes on the destination computer and rebuilds links even when memory IDs are remapped. Browser Bridge v0.14 also lets the user select local files while saving a web chat.


## v0.10 Key vault and disaster recovery

Memory Box can now create an encrypted `*.mbxrecovery` vault for the local X25519 device identity. The recovery vault is protected by a randomly generated `MBR1-...` recovery code using scrypt + AES-256-GCM. The code is shown only to the local user and is intentionally not exposed through MCP.

If the original computer is lost, install Memory Box on a new machine, open **Security / Recovery**, select the `.mbxrecovery` file, and enter the recovery code locally. Memory Box restores the original device identity and device ID so historical `.mboxenc` ciphertext addressed to that identity can be decrypted again. Existing non-empty installations are protected from accidental identity replacement.

The encrypted recovery file may be backed up to a configured Baidu Netdisk/OneDrive/NAS sync folder, but the recovery code is never copied with it. Keep the file and code in separate locations. See `docs/RECOVERY.md`.

## v0.9 End-to-end encrypted device sync

New Baidu Netdisk, OneDrive, NAS, Syncthing and generic sync-folder endpoints default to end-to-end encryption. Memory Box writes `.mboxenc` ciphertext to the shared folder, not readable conversation or attachment bytes. Each device has a local X25519 identity; X25519 + HKDF-SHA-256 wraps a random content key, and AES-256-GCM authenticates and encrypts the session package.

Cloud sync uses **mutual device trust**: the sender must trust the recipient before addressing a key to it, and the recipient must trust the sender before importing its ciphertext. Verify the full fingerprint on both devices before trusting. Existing v0.8 endpoints migrate as `legacy-plaintext` for compatibility; new endpoints default to `e2ee`. LAN transfer is also encrypted in v0.9 and retains the short-lived six-digit pairing code for session authentication.

Baidu Netdisk integration remains local-folder based: Memory Box never requests Baidu passwords, cookies, or tokens. The Baidu desktop client synchronizes only the `.mboxenc` ciphertext generated locally.

`.mboxpack` remains the user-controlled plaintext portable/replay format; `.mboxenc` is the E2EE sync envelope.
