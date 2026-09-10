# Memory Box Transfer Packages (`.mboxpack`)

Memory Box v0.7 uses transfer format v2 to move complete saved AI sessions — memory cards plus linked files — between computers. Import remains backward-compatible with v0.6 transfer-format-v1 packages.

## v2 package layout

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
```

`manifest.json` records transfer ID, source device ID, Memory Box version, export scope, memory/attachment counts and SHA-256 checksums. `memories.json` contains memory cards, tags, provenance and version snapshots. `attachments/index.json` maps content-addressed blobs back to their original filenames and memory IDs. `resume.md` is a portable continuation context. `viewer.html` is an offline replay view.

## Safe import behavior

Memory Box does not perform a generic ZIP extraction. It reads only the known metadata files and attachment blob names matching `attachments/blobs/<64-hex-sha256>`, verifies declared checksums, and then writes validated attachment bytes into Memory Box's managed attachment store.

Every installation gets a stable local `device_id`. On import, memory identity is tracked as `(source_device_id, origin_memory_id)`:

- same transfer imported twice -> skipped rather than duplicated;
- package returns to its source computer -> existing local memory is preserved;
- another computer already has the same `M000xxx` but different content -> imported memory gets a new local ID and the origin mapping is retained;
- attachment links are rebuilt against the remapped local ID;
- byte-identical attachments are deduplicated by SHA-256;
- existing local content is not overwritten by default.

## Export

Entire vault:

```bash
memorybox export-pack MemoryBox-All.mboxpack
```

Selected complete session:

```bash
memorybox session-pack CRAB-Session.mboxpack M000007 M000012
```

By category or search:

```bash
memorybox export-pack Manuscripts.mboxpack --category manuscript
memorybox session-pack CRAB.mboxpack --query CRAB
```

Portable folder instead of one file:

```bash
memorybox session-pack TransferFolder M000007 --folder
```

All linked attachments are included automatically.

## Import

```bash
memorybox inspect-pack CRAB-Session.mboxpack
memorybox import-pack CRAB-Session.mboxpack --open
```

On Windows, the installer associates `.mboxpack` with `MemoryBox-Import.cmd`. After Memory Box is installed, double-clicking a package verifies it, imports memories and attachments, opens the local replay page and starts Memory Box.

## Privacy

`.mboxpack` is portable and **not encrypted** in v0.7. Treat it as a private document. Absolute source paths are intentionally omitted from the package. Do not send packages containing confidential material through untrusted channels.
