# Changelog

## 0.13.0 - 2026-09-10

- Added native Windows desktop shell using pywebview/WebView2.
- Added system tray, minimize-to-tray, local notifications and opt-in Windows login startup.
- Added native drag/drop import for validated Memory Box package files.
- Split Windows release into windowed `MemoryBox.exe` and console `MemoryBox-CLI.exe` so MCP stdio remains reliable.
- Refactored the local HTTP service into a clean start/stop runtime for embedding in the desktop process.
- Kept recovery codes outside MCP and the desktop JS bridge; `.mbxrecovery` remains a human-only local flow.
- Updated bootstrap installer and Windows GitHub Actions build for desktop dependencies and dual executables.
- 71/71 regression tests pass, plus fresh-wheel desktop-entry/server smoke testing.


## 0.12.0 - 2026-09-10

- Rebuilt the local UI as a responsive desktop control center with an Apple-inspired, low-noise visual system.
- Added a real Home dashboard backed by existing Memory Box APIs: disaster readiness, recent memories, E2EE endpoints, insurance status and quick actions.
- Reworked Memories into a compact searchable/filterable list and unified Save, Agent, Sync, Insurance, Recovery and Transfer surfaces.
- Added Light / Dark / Auto appearance stored locally with `prefers-color-scheme` support.
- Added responsive sidebar collapse and mobile bottom navigation.
- Moved the large embedded UI template into `memorybox/ui.py` for maintainability.
- Added UI documentation and desktop/mobile visual QA screenshots.
- No SQLite schema change; schema remains v8.

## 0.11.0 - 2026-09-10

- Added automatic full-library E2EE insurance snapshots with configurable interval and retention.
- Added GREEN/YELLOW/RED disaster-readiness self-test covering SQLite, attachments, cloud recovery files and encrypted backups.
- Added local-only recovery-code verification drill; recovery codes remain unavailable to MCP/AI agents.
- Added optional Windows Task Scheduler helper for insurance wake-ups; installation does not enable it silently.
- Added `insurance_settings` and `insurance_runs`; SQLite schema is now v8.
- Added MCP read/trigger tools for insurance status, health, run-now and latest-snapshot verification without exposing recovery secrets.

## 0.10.0 - 2026-09-10

- Added encrypted `.mbxrecovery` disaster-recovery vaults for device X25519 identities.
- Added randomly generated high-entropy `MBR1-...` recovery codes; codes are never persisted in Memory Box.
- Recovery vaults use scrypt key derivation and AES-256-GCM authenticated encryption.
- Restoring a recovery kit reinstates the original device ID/key fingerprint so historical `.mboxenc` ciphertext remains decryptable after computer loss.
- Added local UI and CLI create/inspect/restore/status/backup workflows; sensitive recovery operations are intentionally not exposed over MCP.
- Added Baidu Netdisk/OneDrive/NAS recovery-file backup support without copying the recovery code.
- Added Windows `.mbxrecovery` file association and hidden-input recovery helper.
- SQLite schema v7 adds non-secret recovery event audit metadata.

## 0.9.0 - 2026-09-10

- Added end-to-end encrypted `.mboxenc` sync envelopes and SQLite schema v6.
- Added per-device X25519 identities and human-verifiable SHA-256 public-key fingerprints.
- Added X25519 + HKDF-SHA-256 key wrapping and AES-256-GCM authenticated content encryption.
- Added mutual trusted-device authorization for cloud/sync-folder imports.
- New sync endpoints default to E2EE; existing v0.8 endpoints migrate as `legacy-plaintext` until explicitly upgraded.
- Added encrypted LAN transfer while retaining the short-lived six-digit pairing-code authentication.
- Added CLI, MCP and UI controls for device identity, trust/revoke, security status and endpoint encryption mode.
- Windows installer registers `.mboxenc` and installs the encryption runtime inside Memory Box's private Python runtime.


## 0.8.0 - 2026-09-10

- Added device-sync endpoints backed by SQLite schema v5.
- Added shared-folder synchronization for Baidu Netdisk / 百度网盘, OneDrive, Nutstore, Syncthing, NAS and generic synchronized folders.
- Added automatic receive monitoring while Memory Box is running, duplicate transfer receipts and cloud-visible device presence records.
- Added Baidu Netdisk folder mode without storing Baidu passwords, cookies or tokens.
- Added short-lived trusted-LAN transfer with device discovery, six-digit pairing code and HMAC authentication; LAN payload confidentiality is intentionally not claimed.
- Added Device Sync UI, CLI commands and MCP tools for configuring, sending, receiving and listing devices.
- Removing a sync endpoint never deletes cloud files.

## 0.7.0 - 2026-09-10

- Added complete-session attachment storage backed by SQLite schema v4 and a SHA-256 content-addressed blob store.
- Added CLI/MCP attachment operations and `session-pack`.
- Upgraded `.mboxpack` to transfer format v2 with real attachment blobs, metadata, integrity checks and ID-remap-safe relationship restoration.
- Preserved backward import compatibility with v0.6 transfer format v1.
- Added attachment links to Resume Context and offline replay.
- Added Memory Box UI and Browser Bridge local-file attachment selection.
- Absolute source paths are excluded from portable packages.
- Expanded regression coverage for deduplication, tamper rejection, cross-device restoration and browser upload/download.

## 0.6.0 - 2026-09-10

- Added portable `.mboxpack` cross-device transfer format and transfer-folder mode.
- Added SHA-256 validated, data-only import that never extracts arbitrary archive paths.
- Added per-installation `device_id` and origin mapping for safe ID collision handling.
- Added idempotent re-import behavior.
- Added offline `viewer.html` conversation/memory replay and portable `resume.md`.
- Added CLI and MCP export/import/inspect tools.
- Added Memory Box UI transfer page with export/download and package upload/import.
- Added Windows `.mboxpack` file association and double-click importer.
- SQLite schema upgraded to v3.


## 0.5.0

- Added bidirectional Chrome/Edge Browser Bridge.
- Added one-click save for selected chat text and current visible conversation.
- Added in-extension local memory browsing/search.
- Added Resume Context copy and safe injection into the current web chat composer; never auto-sends.
- Added stable keyboard shortcut `Alt+Shift+M` for selected text.
- Added `source_uri` to SQLite schema v2 with automatic migration from v0.4 databases.
- Added Windows browser-extension installation helper.
- Added browser extension contract tests and migration tests.


## 0.4.0 - 2026-09-10

- Standalone local Memory Box application backed by SQLite.
- Local web UI for save/list/search/categories/pin/favorite/resume.
- MCP stdio server with 11 memory tools.
- Multi-memory bundle/merge and related-memory retrieval.
- Version snapshots on append.
- UAM v0.3 JSON migration.
- Kimi, WorkBuddy, Cursor, Gemini CLI, Claude Code, Codex CLI and generic adapters.
- WorkBuddy MCP + Skill connector bundle.
- Windows bootstrap installer and GitHub Actions Windows executable build.
