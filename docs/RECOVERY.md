# Memory Box disaster recovery (v0.10)

Memory Box v0.10 adds an encrypted recovery vault for the device X25519 identity used by `.mboxenc` end-to-end encrypted sync.

## Recovery kit

A recovery kit has two independent parts:

1. `*.mbxrecovery` — an encrypted JSON recovery vault containing the device identity secret.
2. `MBR1-...` recovery code — a randomly generated high-entropy code shown only when the vault is created.

The recovery code is not written into the recovery file, SQLite database, Memory Box memories, MCP responses, sync presence files, or cloud backup metadata.

The recovery vault uses scrypt (`N=32768, r=8, p=1`) to derive a 256-bit key from the recovery code, then AES-256-GCM to encrypt and authenticate the device identity payload. The payload contains the original device ID and X25519 private identity required to decrypt historical `.mboxenc` packages addressed to that device.

## Recommended storage

Keep the two parts separate. A practical setup is:

- Store the encrypted `.mbxrecovery` file in Baidu Netdisk / OneDrive / NAS or an offline USB drive.
- Print or write the recovery code and keep it offline in a different location.

Anyone who obtains both parts can assume the recovered device identity and decrypt ciphertext addressed to that identity. Treat the recovery code like a master credential.

## Create

Use the local Memory Box UI: **安全/恢复 → 生成恢复文件 + 恢复码**.

CLI:

```bash
memorybox recovery-create MemoryBox-Recovery.mbxrecovery
```

The CLI prints the generated code once. Do not paste it into an AI conversation.

To copy only the encrypted recovery file into an already configured sync-folder endpoint:

```bash
memorybox recovery-backup MemoryBox-Recovery.mbxrecovery <endpoint-id>
```

The recovery code is never copied.

## Restore on a new computer

Install the same or a newer Memory Box version, then use **安全/恢复 → 恢复旧电脑身份** and select the `.mbxrecovery` file. Enter the recovery code locally.

CLI:

```bash
memorybox recovery-restore MemoryBox-Recovery.mbxrecovery
```

The CLI uses hidden terminal input by default. For unattended tests only, `--code` is available, but it is not recommended because shell history/process listings can expose it.

On Windows, `.mbxrecovery` is associated with `MemoryBox-Recover.cmd`; double-clicking the file opens the local hidden-input recovery flow.

## Existing identity safeguards

If the destination Memory Box already has a different active identity and local memories/sync endpoints, recovery refuses to replace it by default. An explicit `--replace-existing` is required. Before replacement, Memory Box writes a local `device-x25519.pre-recovery-*.json` backup with restricted permissions.

Replacing an identity does not delete memories. It changes the cryptographic device identity and restores the original device ID from the recovery vault.

## Historical ciphertext

After successful recovery, historical `.mboxenc` packages addressed to the recovered public-key fingerprint can be decrypted again, even if the original computer no longer exists.

## AI boundary

Recovery-code entry and recovery-key export/restore are intentionally not exposed as MCP tools. Agents must never ask the user to paste a recovery code into chat or save it as a Memory Box memory.
