---
name: memory-box
description: Local persistent memory for saving, browsing, searching, recalling, merging and resuming conversation/task context across AI agents.
---

# Memory Box

When the user says 保存这段 / 记住刚才 / save this conversation, call `memory_save` with only the relevant conversation context, preserving decisions, constraints, next actions, important facts, and useful verbatim identifiers. Do not save secrets unless the user explicitly asks.

When the user says 打开记忆盒子 / 看记忆列表, call `memory_list` or `memory_categories`.

When the user refers to a stable id such as M000007, call `memory_get`.

When the user asks to continue previous work, call `memory_resume`. If they ask for everything related to a topic/project, call `memory_bundle` first and use the returned context.

Use `memory_append` to extend an existing memory, `memory_related` to find neighbors, and `memory_merge` only when consolidation is useful. Preserve source memories by default.


## Complete-session attachments

When the user wants a local PDF, Word document, image, CSV, source file or log preserved with a memory, use `memory_attach_file`. Use `memory_list_attachments` to inspect restored local files. When exporting to another computer, `memory_export_pack` includes linked attachment bytes automatically; do not reduce the transfer to path-only references.


## Device sync

For a user-configured 百度网盘/Baidu Netdisk synchronized local folder, use `memory_sync_add_folder` with provider `baidu-netdisk`, then `memory_sync_send`, `memory_sync_pull`, and `memory_sync_devices`. Do not request Baidu credentials for folder mode.


## Recovery-code boundary (v0.10)

Recovery codes are local-only master credentials. Never ask the user to paste an `MBR1-...` recovery code into chat and never save it as a memory. Identity recovery is intentionally not exposed through MCP; direct the user to the local Memory Box **安全/恢复** UI or local CLI instead.


## Automatic insurance (v0.11)

The agent may inspect disaster-readiness status and trigger an already-configured insurance snapshot. Never request or transmit the user recovery code; recovery-code verification remains a local-only Memory Box operation.
