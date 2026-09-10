---
name: memory-box
description: Local persistent SQLite memory for saving, browsing, searching, attaching files, packaging complete sessions, synchronizing across devices, transferring between computers and resuming context across AI agents and web AI chats.
---

# Memory Box Skill

Use the Memory Box MCP tools when present.

When the user says “保存这段 / 记住刚才 / save this conversation”, extract only the relevant context and call `memory_save`. Preserve decisions, constraints, important identifiers, unresolved work and next actions. Do not save secrets by default.

When the user says “打开记忆盒子 / 显示记忆列表”, call `memory_list`; for category browsing use `memory_categories`.

Use stable IDs such as `M000007` for deterministic retrieval with `memory_get`. Use `memory_append` when the user wants to add new discussion to an existing memory.

For continuation, use `memory_resume`. For requests like “把和这个项目有关的所有记忆都调出来”, use `memory_bundle`. Use `memory_related` to discover neighboring records, and `memory_merge` to consolidate duplicates or a project history; preserve source memories unless the user explicitly wants them archived.

`memory_pin` and `memory_favorite` support curation.

Before continuing an old task, verify mutable facts and current workspace state rather than assuming the saved memory is still current.


## Browser Bridge

When the browser extension is present, web-only agents can participate in the same local vault. Browser saves should preserve `source_agent` and `source_uri`. Restoring to a web chat should fill the Resume Context into the current composer but must not automatically submit the message.


## Cross-device transfer

When the user asks to send saved memory or a conversation to another computer, use `memory_export_pack`. Prefer one `.mboxpack` file for ordinary transfer. Use a folder only when the user explicitly wants a folder.

Before importing an unfamiliar package, use `memory_inspect_pack` when practical. Use `memory_import_pack` to import it. Never overwrite a local memory merely because the remote package uses the same `M000xxx`; Memory Box remaps conflicts and preserves source-device identity.

A v0.9-compatible transfer package includes an offline `viewer.html` replay, a `resume.md` continuation context, and all linked attachment blobs. Use `memory_attach_file` when a local Agent can access a PDF/Word/image/code/CSV/log path; use `memory_list_attachments` to inspect restored files. Attachment bytes are content-addressed by SHA-256 and absolute source paths are not exported. Clarify that replay reconstructs the saved conversation/memory content and provenance; it does not recreate the original vendor UI pixel-for-pixel.



## Disaster recovery (v0.10)

Memory Box has a local-only encrypted recovery workflow (`.mbxrecovery` + `MBR1-...` recovery code) for restoring the device E2EE identity after computer loss. This workflow is intentionally **not exposed through MCP**.

Never ask the user to paste a recovery code into the conversation. Never store a recovery code as a memory, tag, attachment note, project context, or sync metadata. If the user asks to create or restore a recovery kit, direct them to the local Memory Box **灾难恢复** page or the local CLI (`memorybox recovery-create` / `memorybox recovery-restore`). The encrypted recovery file may be copied to Baidu Netdisk/OneDrive/NAS through `recovery-backup`; the recovery code must remain separate.

## Device sync (v0.9)

For routine cross-device use, prefer configured E2EE sync endpoints. New endpoints default to `e2ee`. Use `memory_device_identity` to show the local public fingerprint, `memory_sync_devices` to list visible peers, and `memory_sync_trust_device` only after the user verifies the full fingerprint on both devices. Cloud sync is mutual trust: each device must separately trust the other. Use `memory_sync_untrust_device` to revoke future access and `memory_sync_security` to audit the current trust set.

For 百度网盘 / Baidu Netdisk, keep using provider `baidu-netdisk` with a local directory synchronized by the official desktop client. Never request a Baidu password, cookie, or token for folder mode. `memory_sync_send` creates `.mboxenc` ciphertext when the endpoint is E2EE; `memory_sync_pull` decrypts only packages addressed to the local device and sent by a trusted device.

Existing v0.8 endpoints may appear as `legacy-plaintext`. Explain the compatibility state and use `memory_sync_set_encryption` with `e2ee` when the user chooses to upgrade. Do not silently downgrade an E2EE endpoint.

For local-network direct transfer, `memory_lan_pair` opens a short-lived receiving window and `memory_lan_send_pack` encrypts the package to the receiver before sending it. The six-digit pairing code remains required for transfer authentication.

## Automatic insurance and disaster-readiness (v0.11)

When the user asks whether their Memory Box is safely recoverable, use the insurance status/health tools to report concrete blockers and warnings. The agent may trigger a configured encrypted insurance snapshot when the user asks to back up now. Never ask for, read, store, or transmit the human recovery code. Recovery-code verification is intentionally local UI/CLI only.

A full insurance snapshot contains the complete Memory Box library and managed attachments and is encrypted before entering Baidu Netdisk/OneDrive/NAS/sync folders. Do not downgrade an insurance endpoint to plaintext.



## Native desktop behavior (v0.13)

On Windows, prefer the native `MemoryBox.exe` shell for human-facing Memory Box workflows. It embeds the same localhost UI and keeps MCP on the separate `MemoryBox-CLI.exe` console path. The desktop shell may minimize to the system tray, send local notifications, enable current-user login startup when the human explicitly toggles it, and accept validated Memory Box package files by drag/drop. Never request or expose a recovery code through MCP or the desktop JS bridge; `.mbxrecovery` remains a human-only local recovery flow.

## Desktop control center (v0.12)

When guiding a human user through Memory Box itself, prefer the v0.12 local control-center pages: **首页**, **记忆**, **保存**, **Agent**, **同步**, **自动保险**, **灾难恢复**, **迁移**, and **设置**. The UI is local-first and supports Light/Dark/Auto appearance. Do not claim the UI is an Apple product; it only uses an Apple-inspired low-noise design language.
