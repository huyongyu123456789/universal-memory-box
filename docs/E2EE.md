# Memory Box E2EE v1

Memory Box v0.9 encrypts sync payloads before they enter cloud or shared-folder storage.

## Primitive suite

- Device key agreement: X25519
- Key derivation: HKDF-SHA-256
- Content encryption: AES-256-GCM with a fresh random 256-bit content key and 96-bit nonce per envelope
- Key wrapping: AES-GCM over the content key using the X25519/HKDF-derived device-to-device key

## Authorization

Cloud sync requires mutual trusted-device records. The sender includes wrapped content keys only for trusted recipients. The recipient also verifies the sender device ID/public key against its own trusted-device record before decryption/import. Fingerprints must be compared out-of-band on both devices.

## Envelope

`.mboxenc` is a streaming binary envelope: magic + authenticated JSON header + ciphertext + GCM tag. The header exposes routing metadata but no conversation or attachment plaintext. The authenticated header binds the transfer ID, sender identity, recipient key slots, cipher suite, nonce and plaintext length to the GCM tag.

## Compatibility

`.mboxpack` remains a plaintext portable/replay capsule. Existing v0.8 sync endpoints migrate to `legacy-plaintext`; new endpoints default to E2EE.
