# Attachments and Complete Session Capsules

Memory Box v0.7 can bind real local files to a saved memory and carry those files across computers inside a `.mboxpack` session capsule.

## Storage model

Attachment bytes are copied into the Memory Box managed store and addressed by SHA-256. The database stores metadata and memory-to-attachment links; it does not depend on the original absolute file path after attachment.

Default locations:

- Windows: `%LOCALAPPDATA%\MemoryBox\attachments\<sha-prefix>\<sha256>`
- macOS/Linux: `~/.memorybox/attachments/<sha-prefix>/<sha256>`

The same byte-identical file linked to multiple memories is stored only once.

## Attach a file

```bash
memorybox attach M000007 "C:\path\paper.pdf" --note "reviewed manuscript"
memorybox attachments M000007
```

You can also save and attach in one CLI call:

```bash
memorybox save "conversation summary" --attach paper.pdf --attach figure.png
```

Connected local MCP agents can use `memory_attach_file`. Browser users can select local files in the Memory Box UI or Browser Bridge; web upload is intentionally size-limited, while MCP/CLI supports larger local files.

## Transfer package v2

A v0.7 `.mboxpack` contains:

```text
manifest.json
memories.json
resume.md
viewer.html
README.txt
attachments/
  index.json
  blobs/
    <sha256>
    <sha256>
```

`attachments/index.json` records original filename, MIME type, byte length, hash, role/note, and which original memory IDs reference each blob. Absolute source paths are deliberately excluded.

On import, Memory Box validates every declared checksum before storing bytes. Blobs are written into the destination computer's managed attachment store and links are rebuilt against the locally mapped memory IDs. ID remapping therefore does not break attachment associations.

## Replay behavior

After import, Memory Box writes a safe replay receipt under its `imports/<transfer-id>/` directory. The local `viewer.html` shows saved conversation content and attachment links; `resume.md` contains a destination-side Resume Context with restored local attachment paths for agents that can open local files.

Replay means reconstructing the saved content, metadata, provenance, and attached files. It does not clone the vendor's original ChatGPT/Kimi/Claude UI or recover cloud-side messages/files that were never captured by Memory Box.

## Security

- Attachment blobs are verified with SHA-256 on export and import.
- Package paths are never blindly extracted.
- Only known metadata files and hash-named attachment blobs are read.
- Absolute source paths are not exported.
- Packages are not encrypted; treat `.mboxpack` as a private document.
