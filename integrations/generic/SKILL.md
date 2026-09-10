---
name: memory-box
description: Use a local Memory Box MCP server to save chats, attach local files, move complete sessions across computers, and resume cross-agent memory.
---

# Memory Box generic agent behavior

Prefer MCP tools when available. Natural-language triggers:

- "保存这段 / remember this" -> `memory_save`
- "把这个 PDF/Word/图片/代码也挂到这条记忆" -> `memory_attach_file`
- "这条记忆有哪些附件" -> `memory_list_attachments`
- "打开记忆列表" -> `memory_list`
- "有哪些分类" -> `memory_categories`
- "打开 M000007" -> `memory_get`
- "追加到 M000007" -> `memory_append`
- "恢复 M000007 并继续" -> `memory_resume`
- "把与 X 有关的记忆都调出来" -> `memory_bundle`
- "把这段完整会话打包发到另一台电脑" -> `memory_export_pack` (linked attachments are included automatically)

When a local file is relevant to future continuation and the user asks to preserve it, attach the file itself rather than saving only its path. Memory Box copies files into a SHA-256-addressed store, so original paths can disappear without breaking the memory.

Before resuming execution, verify mutable workspace facts. Do not expose or persist credentials by default.


## Device sync

- “把 M000007 发到百度网盘同步盒” -> `memory_sync_send`
- “检查百度网盘/同步目录的新记忆” -> `memory_sync_pull`
- “把这个同步目录接进来” -> `memory_sync_add_folder` (use provider `baidu-netdisk` for 百度网盘)
- “看看还有哪些电脑” -> `memory_sync_devices`

Baidu folder mode uses an already synchronized local folder and must not request passwords/cookies. In v0.9, cloud-folder and LAN sync use E2EE; cloud sync requires mutual trusted-device fingerprint verification.


## Recovery-code boundary (v0.10)

Recovery codes are local-only master credentials. Never ask the user to paste an `MBR1-...` recovery code into chat and never save it as a memory. Identity recovery is intentionally not exposed through MCP; direct the user to the local Memory Box **安全/恢复** UI or local CLI instead.


## Automatic insurance (v0.11)

The agent may inspect disaster-readiness status and trigger an already-configured insurance snapshot. Never request or transmit the user recovery code; recovery-code verification remains a local-only Memory Box operation.
