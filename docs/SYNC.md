# Memory Box device sync (v0.9)

Memory Box v0.9 adds two cross-device transport modes on top of `.mboxenc`:

1. **Shared sync folders** — recommended for routine cross-device use. This works with Baidu Netdisk / 百度网盘, OneDrive, Nutstore, Syncthing, NAS shares, and any folder that another sync product mirrors between computers.
2. **Encrypted LAN direct send** — short-lived receiver window with a six-digit pairing code. v0.9 encrypts the payload to the receiver's X25519 key before transport and also uses the pairing code/HMAC to authenticate the transfer.

## Baidu Netdisk / 百度网盘

The implemented v0.9 integration is local-folder based. Memory Box never requests or stores your Baidu account password, cookie, or access token.

1. Install/sign in to the official Baidu Netdisk desktop client and choose a local folder that is actually synchronized between your computers.
2. Open Memory Box → **设备同步**.
3. Choose **百度网盘 / Baidu Netdisk** and select that synchronized local folder.
4. Memory Box creates `MemoryBoxSync/` inside it. New endpoints default to E2EE and write `.mboxenc` files atomically under `MemoryBoxSync/packages/<device-id>/`.
5. Configure the same cloud-synchronized folder on the second computer.
6. On both computers, open **可信设备**, compare the complete X25519 fingerprints on both screens, and explicitly trust each other. Cloud sync requires mutual trust.
7. While Memory Box is running, the sync monitor checks configured endpoints for new ciphertext, verifies the trusted sender, decrypts locally, then validates/imports the inner `.mboxpack`.

The folder marker and device-presence records do not include source document paths or credentials. Removing a sync endpoint from Memory Box never deletes cloud files.

Baidu's official open platform supports OAuth authorization and Netdisk read/write scopes. Direct OAuth/API integration is intentionally not enabled in v0.9 because an open-source distribution should not ship a shared secret or scrape cookies; a future adapter can support user-owned OAuth application credentials.

## Sync-folder layout

```text
<your synchronized folder>/
└── MemoryBoxSync/
    ├── memorybox-sync.json
    ├── devices/
    │   ├── <device-a>.json
    │   └── <device-b>.json
    └── packages/
        ├── <device-a>/
        │   └── <transfer-id>.mboxenc
        └── <device-b>/
            └── <transfer-id>.mboxenc
```

Each `.mboxenc` provides AES-GCM authenticated encryption; after decryption, the inner `.mboxpack` SHA-256 manifest is validated as a second integrity layer. Duplicate transfers are recorded in SQLite `sync_receipts` and are not imported again. Existing memory-ID conflict remapping still applies.

## CLI

```bash
# Configure a Baidu Netdisk synchronized folder
memorybox sync-add "D:\\BaiduNetdisk\\MemoryBoxShared" --provider baidu-netdisk

# List endpoints
memorybox sync-endpoints

# Inspect this device fingerprint and visible peers
memorybox identity
memorybox sync-devices <endpoint-id>

# On BOTH machines, verify the displayed fingerprint and trust the other device
memorybox sync-trust <endpoint-id> <remote-device-id> --fingerprint <full-fingerprint>

# Publish selected memory
memorybox sync-send <endpoint-id> --id M000027

# Publish a topic or category
memorybox sync-send <endpoint-id> --query CRAB
memorybox sync-send <endpoint-id> --category manuscript

# Receive new packages
memorybox sync-pull <endpoint-id>

# Show devices visible in this shared folder
memorybox sync-devices <endpoint-id>
```

## Agent/MCP examples

An MCP-connected agent can interpret requests such as:

- “把 M000027 发到百度网盘同步盒。” → `memory_sync_send`
- “检查百度网盘有没有另一台电脑的新记忆。” → `memory_sync_pull`
- “列出这个百度同步目录里看到的设备。” → `memory_sync_devices`
- “显示本机加密指纹。” → `memory_device_identity`
- “我已经核对两台电脑指纹，信任这台设备。” → `memory_sync_trust_device`
- “把这个百度网盘同步目录接到 Memory Box。” → `memory_sync_add_folder`

## Trusted-LAN mode

On receiving computer B, open **设备同步 → 开启 5 分钟接收**. It displays a six-digit pairing code. On computer A, discover the receiver, type the code shown on B, and send. Packages are still validated as normal `.mboxenc` data before import.

v0.9 LAN confidentiality comes from the same X25519 + AES-256-GCM envelope used for cloud sync. The pairing code/HMAC remains an independent user-confirmation and transfer-authentication layer. As with any local discovery protocol, prefer networks you control and verify the receiver shown in the UI.
