# Memory Box Local Neural Retrieval — v0.16

Memory Box v0.16 supports an optional **BAAI/bge-small-zh-v1.5** neural embedding backend through **FastEmbed/ONNX Runtime**. FastEmbed lists this model as a supported 512-dimensional Chinese embedding model of roughly 0.09 GB, and the BGE model is MIT licensed.

## Privacy contract

- Normal search never downloads a model.
- `model-install` is an explicit user action.
- Once installed, retrieval instantiates FastEmbed with `local_files_only=True`.
- If the neural runtime/model is unavailable, Memory Box falls back to `hashing-v1` and remains usable.

## Commands

```bash
memorybox model-status
memorybox model-install
memorybox model-install --from-dir /path/to/offline/model-cache
memorybox model-remove
memorybox vectors-rebuild
```

The managed cache is stored under the Memory Box data directory in `models/bge-small-zh-v1.5-fastembed/`. Full desktop release workflows can bundle that cache so end users do not have to configure a model path.
