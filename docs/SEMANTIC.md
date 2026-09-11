# Local Semantic Retrieval (v0.16)

Memory Box combines lexical/project ranking with a local vector signal. The fallback backend is `hashing-v1`. v0.16 adds an optional neural backend using **BAAI/bge-small-zh-v1.5** via **FastEmbed/ONNX Runtime**.

## Safety and privacy

- Retrieval never downloads models.
- Neural model installation is an explicit human action or release-build step.
- Once installed, FastEmbed is opened with `local_files_only=True`.
- If the model/runtime cannot be loaded, search falls back to `hashing-v1`.
- Memory text is not sent to a remote embedding API.

## Commands

```bash
memorybox semantic-status
memorybox model-status
memorybox model-install
memorybox model-install --from-dir /offline/model/cache
memorybox model-remove
memorybox vectors-rebuild
memorybox vector-search "query"
```

Vector rows remain cached in SQLite in `memory_vectors`, keyed by memory ID, backend and content hash. Changing the active backend naturally creates a separate cache namespace.
