# Memory Box

**Local-first SQLite memory and an MCP bridge for AI agents.**

Memory Box stores durable conversation/task context on the user's own machine and exposes it through MCP, CLI, and a local UI. Save once, then recall or resume from Kimi Code, WorkBuddy, Cursor, Gemini CLI, Claude Code, Codex CLI, or any MCP-capable agent.



## v0.16 Local Neural Retrieval + Windows/macOS/HarmonyOS release foundation

Memory Box v0.16 productizes semantic retrieval with an optional **BAAI/bge-small-zh-v1.5** backend through **FastEmbed/ONNX Runtime**. The model is 512-dimensional and is installed only by an explicit installer/build step; normal search never downloads model files. Once present, retrieval forces local-only model loading and falls back safely to `hashing-v1` if the neural runtime is unavailable.

This release also expands the desktop product line beyond Windows. Windows keeps the native pywebview/WebView2 shell. macOS now has a Cocoa/WebKit build workflow that produces `MemoryBox.app` and a `.dmg`, with Developer ID signing/notarization hooks for smooth external double-click launch. HarmonyOS NEXT gets a separate native **ArkTS/ArkUI Stage-model** project backed by HarmonyOS `relationalStore`, rather than pretending the Python desktop shell is a native HarmonyOS app.

```bash
memorybox model-status
memorybox model-install
memorybox vectors-rebuild
memorybox vector-search "OmpA mechanism"
```

See `docs/NEURAL_MODEL.md`, `docs/PLATFORMS.md`, `macos/README.md`, and `harmonyos/MemoryBoxHarmony/README.md`.

## v0.14 Project Workspaces + Smart Retrieval

Memory Box now treats long-running work as a first-class **Project Workspace** instead of a loose pile of cards. A project has a stable `P000001` ID, summary, current state, next action, lifecycle status and linked memories. The local smart-search engine ranks memories using weighted title/summary/tag/content evidence, project context, recency, pin/favorite signals and approximate text matching. It stays offline and dependency-free; v0.14 does **not** claim a neural embedding model.

```bash
memorybox project-create "CRAB manuscript" --summary "Audited manuscript revision" --current-state "Stage 2 complete" --next-action "Verify Tier-A evidence"
memorybox project-add P000001 M000007 --role evidence
memorybox smart-search "Tier-A verification" --project P000001
memorybox project-resume P000001
```

`.mboxpack` transfer format v3 carries project metadata and memory links, so a project moved to another computer remains a project instead of becoming unrelated memory cards.

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

- First-class Project Workspaces with state, next action and project-level resume
- Local hybrid retrieval with vector similarity and transparent ranking signals
- Review-first duplicate detection and explicit project-safe merge
- Derived project summary/state/next-action fields that never overwrite curated fields
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

## Quick start

Windows: extract the release and double-click `Install-MemoryBox.cmd`. v0.16 also installs the lightweight FastEmbed runtime and attempts a one-time pinned BGE model download unless `MEMORYBOX_SKIP_NEURAL_MODEL=1` is set. The bootstrap installs into `%LOCALAPPDATA%\MemoryBox`, downloads an isolated Python runtime on first install, creates a Start Menu shortcut, opens the local UI, and performs a one-time auto-link scan for detected local MCP agents. Set `MEMORYBOX_NO_AUTOLINK=1` to disable auto-linking.

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

### macOS

Use the GitHub `Build macOS desktop app` workflow to produce `MemoryBox.app` inside a `.dmg`. A Developer ID certificate plus Apple notarization credentials are required for frictionless distribution to other Macs; without them the workflow creates an ad-hoc signed development artifact.

### HarmonyOS NEXT

Open `harmonyos/MemoryBoxHarmony` in DevEco Studio. It is a native ArkTS/ArkUI Stage-model project with a local RDB foundation and the red cavalry icon. Release HAP/APP signing requires the publisher's AppGallery Connect credentials.

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

`memory_save`, `memory_list`, `memory_get`, `memory_append`, `memory_categories`, `memory_resume`, `memory_related`, `memory_bundle`, `memory_merge`, `memory_pin`, `memory_favorite`, `memory_smart_search`, `memory_project_create`, `memory_projects`, `memory_project_get`, `memory_project_update`, `memory_project_add`, `memory_project_remove`, `memory_project_suggest`, `memory_project_resume`, `memory_device_identity`, `memory_sync_add_folder`, `memory_sync_endpoints`, `memory_sync_detect`, `memory_sync_devices`, `memory_sync_trust_device`, `memory_sync_untrust_device`, `memory_sync_security`, `memory_sync_set_encryption`, `memory_sync_send`, `memory_sync_pull`, `memory_lan_pair`, `memory_lan_discover`, `memory_lan_send_pack`.

## Tests

```bash
python -m unittest discover -s tests -v
```

MIT License.


## Browser Bridge v0.13

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

Attach real PDFs, Word files, images, CSVs, code and logs to a memory with `memorybox attach` or the `memory_attach_file` MCP tool. Files are copied into a local SHA-256-addressed store and deduplicated. `session-pack` / `export-pack` automatically carries linked files inside transfer-format-v2 `.mboxpack` capsules. Import restores the bytes on the destination computer and rebuilds links even when memory IDs are remapped. Browser Bridge v0.13 also lets the user select local files while saving a web chat.


## v0.10 Key vault and disaster recovery

Memory Box can now create an encrypted `*.mbxrecovery` vault for the local X25519 device identity. The recovery vault is protected by a randomly generated `MBR1-...` recovery code using scrypt + AES-256-GCM. The code is shown only to the local user and is intentionally not exposed through MCP.

If the original computer is lost, install Memory Box on a new machine, open **Security / Recovery**, select the `.mbxrecovery` file, and enter the recovery code locally. Memory Box restores the original device identity and device ID so historical `.mboxenc` ciphertext addressed to that identity can be decrypted again. Existing non-empty installations are protected from accidental identity replacement.

The encrypted recovery file may be backed up to a configured Baidu Netdisk/OneDrive/NAS sync folder, but the recovery code is never copied with it. Keep the file and code in separate locations. See `docs/RECOVERY.md`.

## v0.9 End-to-end encrypted device sync

New Baidu Netdisk, OneDrive, NAS, Syncthing and generic sync-folder endpoints default to end-to-end encryption. Memory Box writes `.mboxenc` ciphertext to the shared folder, not readable conversation or attachment bytes. Each device has a local X25519 identity; X25519 + HKDF-SHA-256 wraps a random content key, and AES-256-GCM authenticates and encrypts the session package.

Cloud sync uses **mutual device trust**: the sender must trust the recipient before addressing a key to it, and the recipient must trust the sender before importing its ciphertext. Verify the full fingerprint on both devices before trusting. Existing v0.8 endpoints migrate as `legacy-plaintext` for compatibility; new endpoints default to `e2ee`. LAN transfer is also encrypted in v0.9 and retains the short-lived six-digit pairing code for session authentication.

Baidu Netdisk integration remains local-folder based: Memory Box never requests Baidu passwords, cookies, or tokens. The Baidu desktop client synchronizes only the `.mboxenc` ciphertext generated locally.

`.mboxpack` remains the user-controlled plaintext portable/replay format; `.mboxenc` is the E2EE sync envelope.
