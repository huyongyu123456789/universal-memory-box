from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from .db import default_home, utc_now

# FastEmbed publishes this model as a supported 512-dim, ~90 MB Chinese BGE model.
DEFAULT_MODEL_ID = "BAAI/bge-small-zh-v1.5"
DEFAULT_MODEL_DIM = 512
DEFAULT_MODEL_DIRNAME = "bge-small-zh-v1.5-fastembed"
MODEL_LICENSE = "MIT"
MARKER = "memorybox-model.json"


def models_home(home: Path | None = None) -> Path:
    return Path(home or default_home()) / "models"


def managed_model_path(home: Path | None = None) -> Path:
    return models_home(home) / DEFAULT_MODEL_DIRNAME


def marker_path(home: Path | None = None) -> Path:
    return managed_model_path(home) / MARKER


def _read_marker(path: Path) -> dict[str, Any] | None:
    p = path / MARKER
    if not p.is_file():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(obj, dict) and obj.get("model_id") == DEFAULT_MODEL_ID:
            return obj
    except Exception:
        pass
    return None



def bundled_model_candidates() -> list[Path]:
    out: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        # Windows one-dir / portable release.
        out.append(exe_dir / "models" / DEFAULT_MODEL_DIRNAME)
        # macOS .app: Contents/MacOS/MemoryBox -> Contents/Resources/models/...
        out.append(exe_dir.parent / "Resources" / "models" / DEFAULT_MODEL_DIRNAME)
        mei = getattr(sys, "_MEIPASS", None)
        if mei:
            out.append(Path(mei) / "models" / DEFAULT_MODEL_DIRNAME)
    else:
        out.append(Path(__file__).resolve().parents[1] / "models" / DEFAULT_MODEL_DIRNAME)
    return out


def active_model_path(home: Path | None = None) -> Path | None:
    env = (os.environ.get("MEMORYBOX_EMBEDDING_MODEL") or "").strip()
    if env:
        p = Path(env).expanduser()
        if _read_marker(p):
            return p
    for p in [*bundled_model_candidates(), managed_model_path(home)]:
        if _read_marker(p):
            return p
    return None

def model_status(home: Path | None = None) -> dict[str, Any]:
    target = managed_model_path(home)
    active = active_model_path(home)
    marker = _read_marker(active) if active else None
    try:
        import fastembed  # type: ignore  # noqa: F401
        runtime = True
    except Exception:
        runtime = False
    return {
        "model_id": DEFAULT_MODEL_ID,
        "dimension": DEFAULT_MODEL_DIM,
        "license": MODEL_LICENSE,
        "installed": bool(marker),
        "runtime_available": runtime,
        "ready": bool(marker and runtime),
        "cache_dir": str(active or target),
        "managed_cache_dir": str(target),
        "bundled": bool(active and active != target),
        "marker": marker or {},
        "local_only_after_install": True,
        "download_is_explicit": True,
    }


def install_model(*, source_dir: str | os.PathLike[str] | None = None, home: Path | None = None) -> dict[str, Any]:
    """Install the optional neural model.

    - source_dir: copy a previously downloaded Memory Box model cache fully offline.
    - no source_dir: explicitly download the supported FastEmbed BGE model.

    Search/retrieval never calls this automatically, so normal use cannot trigger an
    unexpected network model download.
    """
    target = managed_model_path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(target.name + ".installing")
    shutil.rmtree(staging, ignore_errors=True)

    try:
        from fastembed import TextEmbedding  # type: ignore
    except Exception as exc:
        raise RuntimeError("Neural runtime is not installed. Install Memory Box semantic extras: pip install 'memory-box-agent-memory[semantic]'.") from exc

    if source_dir:
        src = Path(source_dir).expanduser().resolve()
        if not src.is_dir():
            raise ValueError(f"model cache directory does not exist: {src}")
        shutil.copytree(src, staging)
        method = "offline-cache-copy"
    else:
        staging.mkdir(parents=True, exist_ok=True)
        # This is the only code path allowed to fetch model files. It is user-triggered.
        model = TextEmbedding(model_name=DEFAULT_MODEL_ID, cache_dir=str(staging), local_files_only=False)
        # Force model initialization and validate output shape before marking installed.
        vec = list(model.embed(["Memory Box semantic model installation check"]))[0]
        if len(vec) != DEFAULT_MODEL_DIM:
            raise RuntimeError(f"unexpected embedding dimension: {len(vec)}")
        method = "fastembed-download"

    # Validate the cache without network access. If the copied cache is incomplete,
    # FastEmbed raises here and no marker is written.
    model = TextEmbedding(model_name=DEFAULT_MODEL_ID, cache_dir=str(staging), local_files_only=True)
    vec = list(model.embed(["记忆盒 本地语义模型 自检"]))[0]
    if len(vec) != DEFAULT_MODEL_DIM:
        raise RuntimeError(f"invalid model cache: expected {DEFAULT_MODEL_DIM} dims, got {len(vec)}")

    metadata = {
        "model_id": DEFAULT_MODEL_ID,
        "dimension": DEFAULT_MODEL_DIM,
        "license": MODEL_LICENSE,
        "installed_at": utc_now(),
        "method": method,
        "runtime": "fastembed/onnxruntime",
    }
    (staging / MARKER).write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if target.exists():
        backup = target.with_name(target.name + ".previous")
        shutil.rmtree(backup, ignore_errors=True)
        target.replace(backup)
    staging.replace(target)
    return {"ok": True, **metadata, "cache_dir": str(target)}


def uninstall_model(home: Path | None = None) -> dict[str, Any]:
    target = managed_model_path(home)
    shutil.rmtree(target, ignore_errors=True)
    return {"ok": True, "cache_dir": str(target), "installed": False}
