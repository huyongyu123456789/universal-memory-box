# Memory Box automatic insurance (v0.11)

Automatic insurance is a disaster-readiness layer on top of Memory Box E2EE sync and recovery vaults.

## What it protects

A scheduled insurance run exports the complete memory library, including archived memories, version history, tags, source metadata and every managed attachment. The complete transfer snapshot is encrypted **before** it enters the configured Baidu Netdisk / OneDrive / NAS / synced folder.

Insurance snapshots are written under:

`MemoryBoxSync/insurance/<device-id>/insurance-<timestamp>-<transfer-id>.mboxenc`

They are addressed to the local Memory Box X25519 identity. A replacement computer can decrypt them after the original identity has been recovered from a `.mbxrecovery` vault.

## Configure

```bash
memorybox insurance-configure <endpoint-id> --interval-hours 24 --retention 7 --deep-verify
memorybox insurance-run --force
memorybox insurance-health --deep
```

The endpoint must use E2EE. Plaintext endpoints are rejected.

## Health states

- **GREEN**: no blocking problem was detected and no outstanding warning remains.
- **YELLOW**: core recovery material exists, but a recommended condition needs attention (for example, a recovery file is only local or the recovery-code drill is stale).
- **RED**: an actual blocker exists, such as a corrupt database, missing attachment, unavailable E2EE endpoint, missing recovery vault or no usable encrypted insurance snapshot.

The automatic health check **cannot know whether the human still possesses the recovery code**. Use the local recovery-code verification drill periodically:

```bash
memorybox recovery-verify MemoryBox-Recovery.mbxrecovery
```

The code is requested with hidden local input. It is not exposed through MCP.

## Background execution

When the Memory Box UI is open, `InsuranceMonitor` checks whether a backup is due. Windows users can additionally run `Enable-Auto-Insurance.cmd` to create an hourly Task Scheduler wake-up. The task only invokes `insurance-run`; the configured interval still controls whether a new backup is actually created.

The scheduled task is **not enabled silently during installation**.
