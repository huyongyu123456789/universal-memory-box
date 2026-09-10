# Architecture

```text
AI Agent
  │
  ├─ MCP stdio ─────────┐
  ├─ CLI ───────────────┤
  └─ local REST/UI ─────┤
                        ▼
                  Memory Box Core
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
        SQLite memory DB     Agent adapters
        + FTS5 search        Kimi / WorkBuddy
        + versions           Cursor / Gemini
        + tags/categories    Claude / Codex
        + flags              CodeBuddy / Qoder
```

The database is the source of truth. Agent adapters only expose or register access; they do not own memory state. The MCP layer deliberately provides small, vendor-neutral tools so a new agent can save, browse, search and resume without importing a vendor-specific transcript format.

The local HTTP UI binds to `127.0.0.1`. Direct public-network exposure is out of scope.


## Transfer layer (v0.6)

`memorybox.transfer` implements a portable package boundary above SQLite. Export serializes selected cards, tags, provenance and version snapshots into a data-only `.mboxpack`; import validates SHA-256 and tracks remote identity using `(source_device_id, origin_memory_id)`. This makes transfers idempotent and avoids destructive ID collision behavior. A generated `viewer.html` provides offline replay, while `resume.md` is the cross-agent continuation payload.

## Attachment/session layer (v0.7)

SQLite schema v4 separates attachment metadata from memory links. Attachment bytes live outside SQLite in a SHA-256-addressed managed blob store, allowing deduplication and efficient transfer. Transfer format v2 serializes only portable metadata and hash-named blobs; absolute source paths never cross machines. Destination import rebuilds links after memory-ID conflict mapping, then generates a local replay receipt and Resume Context that point to destination-side attachment paths.


## Device-sync and E2EE layer (v0.9)

SQLite schema v6 added `encryption_mode` to sync endpoints plus `trusted_devices`. SQLite schema v7 adds non-secret `recovery_events` audit metadata. SQLite schema v8 adds automatic-insurance settings and run history. New endpoints default to `e2ee`; schema-v5 endpoints migrate as `legacy-plaintext` so upgrades do not silently change an existing workflow.

Each installation owns an X25519 device identity. Shared-folder presence files expose only the public key/fingerprint and routing metadata. Trust is local and explicit. Cloud sync is mutual trust: the sender creates recipient key slots only for trusted devices, while the recipient also checks the sender ID/public key against its own trusted-device record.

The normal `.mboxpack` complete-session capsule is created only in a temporary local directory. E2EE endpoints wrap it into a streaming `.mboxenc` envelope before publishing to `MemoryBoxSync/packages/<device-id>/`. The envelope uses X25519 + HKDF-SHA-256 to derive a device-to-device key-wrapping key and AES-256-GCM for authenticated content encryption. Conversation text and attachment blobs are ciphertext before Baidu Netdisk, OneDrive, NAS or another sync layer sees them.

The `baidu-netdisk` provider remains intentionally local-folder based: synchronization to Baidu is performed by the user's Baidu Netdisk client and the core stores no Baidu password, cookie or OAuth token. LAN direct transfer uses the same E2EE envelope and additionally keeps the short-lived six-digit pairing-code HMAC authentication.


## Disaster-recovery layer (v0.10)

`memorybox/recovery.py` creates and restores encrypted `.mbxrecovery` identity vaults. Recovery secrets are kept outside MCP and ordinary memory records. See `docs/RECOVERY.md`.


## Automatic insurance layer (v0.11)

`insurance.py` builds a complete transfer-format snapshot, validates managed attachment availability, encrypts it to the local device identity, writes it under the selected E2EE sync endpoint, applies retention, and exposes disaster-readiness checks. `InsuranceMonitor` runs only while the app is active; Windows users can opt into the packaged Task Scheduler helper for periodic wake-ups.
