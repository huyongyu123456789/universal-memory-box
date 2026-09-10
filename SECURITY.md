# Security

Memory Box is local-first. Memories and attachments stay on the user's machine unless the user deliberately exports or transmits them.

## Local data

The SQLite database contains conversation-derived information. The managed attachment store may contain original PDFs, Word files, images, source code, logs, datasets and other sensitive files. Protect the Memory Box home directory with normal OS account and disk security.

Do not store API keys, passwords, private keys or authentication tokens in memories unless you intentionally accept that risk. Agent instructions should avoid saving secrets by default.

## Complete-session `.mboxpack` files

v0.7 transfer-format-v2 packages can contain both conversation content and real attachment bytes. They are portable but **not encrypted**.

Import is deliberately data-only:

- Memory Box never performs a generic ZIP extraction.
- It reads only known metadata files and hash-named `attachments/blobs/<sha256>` entries.
- Every declared file is checked against the SHA-256 manifest before import.
- Attachment byte length and SHA-256 are rechecked before they enter the managed store.
- Absolute source filesystem paths are not exported.
- A remote `M000xxx` conflict never overwrites different local content; IDs are remapped and attachment links follow the mapping.
- Byte-identical attachments are deduplicated by hash.

Treat `.mboxpack` files like private documents. Do not send confidential capsules over untrusted channels.

## Browser bridge

The Browser Bridge talks only to `127.0.0.1:8765` by default. Restoring context fills an AI website's composer but does not click Send automatically. Browser-side file selection requires an explicit user file-picker action; the extension does not silently crawl arbitrary local files.

## Agent configuration

Before Memory Box edits supported JSON MCP configuration files, it creates a timestamped backup. Malformed JSON is not overwritten automatically.

Report security issues privately to the repository owner rather than opening a public issue with exploit details or sensitive data.


## Device sync security (v0.9)

New sync endpoints use end-to-end encrypted `.mboxenc` envelopes. Memory Box uses X25519 device keys, HKDF-SHA-256 and AES-256-GCM through the `cryptography` package. Cloud-folder providers receive ciphertext plus limited routing metadata (device IDs, transfer ID, recipient IDs/fingerprints and approximate package size); conversation text and attachment bytes are encrypted.

Cloud imports require mutual trust. A sender only addresses future keys to trusted recipient devices, and a recipient only decrypts/imports ciphertext whose sender device and public key match its own trusted-device record. Compare the full fingerprint on both devices before trusting. Revocation affects future packages; it cannot erase plaintext or keys already received by a previously trusted device.

The device private key is stored under the local Memory Box `keys/` directory and must be protected like a credential. It is never written into Baidu Netdisk presence files. Deleting the active key can make historical ciphertext addressed only to that identity unrecoverable unless a v0.10 encrypted recovery kit exists. Create a `.mbxrecovery` vault and store its recovery code separately.

Existing v0.8 sync endpoints migrate as `legacy-plaintext` to preserve compatibility and must be explicitly upgraded. An E2EE endpoint rejects/ignores plaintext `.mboxpack` files found in its shared sync folder, preventing silent downgrade imports.

LAN transfer in v0.9 encrypts the package to the receiver's X25519 public key and authenticates the transfer with the short-lived six-digit pairing code/HMAC. The pairing code is still required; encryption does not replace user confirmation.



## Disaster-recovery security (v0.10)

The `.mbxrecovery` file contains the device identity private key only after encryption with a key derived from a high-entropy recovery code using scrypt. AES-256-GCM provides authenticated encryption. The recovery code is not persisted by Memory Box and is never exposed as an MCP tool.

Keep the encrypted recovery file and recovery code separate. Possession of both is equivalent to possession of the recovered device private identity and may allow decryption of historical `.mboxenc` packages addressed to that key. Do not place the recovery code in AI chats, memories, cloud notes, source repositories, shell scripts, or the same sync folder as the recovery file.

Restoring over a different active identity on a non-empty Memory Box requires an explicit replacement flag and creates a local backup of the previous key first.

## Automatic-insurance security (v0.11)

Automatic insurance refuses plaintext sync endpoints. Full snapshots are exported locally, encrypted to the active device X25519 identity, and only then copied into the configured sync folder. The recovery-code drill is local-only and is not exposed through MCP. A GREEN health result still assumes the user has retained the recovery code; software cannot prove physical/offline possession without the user entering it.

Scheduled background insurance is opt-in on Windows. The scheduled task runs the local `insurance-run` command and receives no recovery code, private key, cloud credential, or cookie.
