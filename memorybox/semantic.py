from __future__ import annotations

import hashlib
import math
import os
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .db import _connect, init_db, utc_now
from .model_manager import model_status, active_model_path, DEFAULT_MODEL_ID, DEFAULT_MODEL_DIM

DEFAULT_DIM = 768
HASHING_BACKEND = "hashing-v1"
_MODEL_CACHE: dict[str, Any] = {}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _features(text: str) -> list[tuple[str, float]]:
    """Dependency-free local features used by the fallback vector backend.

    Word, CJK bigram and character n-gram features make approximate wording
    more robust than plain keyword matching while keeping data fully local.
    """
    t = _normalize_text(text)
    if not t:
        return []
    out: list[tuple[str, float]] = []
    words = re.findall(r"[a-z0-9][a-z0-9_.+\-/]{1,}", t)
    out.extend(("w:" + w, 1.0) for w in words)
    for a, b in zip(words, words[1:]):
        out.append(("wb:" + a + " " + b, 0.65))
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", t):
        out.append(("cjk:" + chunk, 0.8))
        out.extend(("cj2:" + chunk[i:i+2], 1.0) for i in range(len(chunk) - 1))
        if len(chunk) >= 3:
            out.extend(("cj3:" + chunk[i:i+3], 0.7) for i in range(len(chunk) - 2))
    compact = re.sub(r"\s+", " ", t)
    # Character n-grams help with spelling variation and compact technical identifiers.
    if len(compact) <= 12000:
        for n, weight in ((3, 0.18), (4, 0.14)):
            for i in range(max(0, len(compact) - n + 1)):
                gram = compact[i:i+n]
                if gram.strip():
                    out.append((f"ch{n}:" + gram, weight))
    return out


def _hash_index(feature: str, dim: int) -> tuple[int, float]:
    d = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    n = int.from_bytes(d, "little")
    return n % dim, (-1.0 if (n >> 63) else 1.0)


def hashing_embed(text: str, dim: int = DEFAULT_DIM) -> list[float]:
    vec = [0.0] * dim
    for feat, weight in _features(text):
        idx, sign = _hash_index(feat, dim)
        vec[idx] += sign * weight
    norm = math.sqrt(sum(v * v for v in vec))
    if norm:
        vec = [v / norm for v in vec]
    return vec


def _pack(vec: Iterable[float]) -> bytes:
    vals = list(vec)
    return struct.pack(f"<{len(vals)}f", *vals)


def _unpack(blob: bytes, dim: int) -> list[float]:
    if len(blob) != dim * 4:
        raise ValueError("invalid vector blob length")
    return list(struct.unpack(f"<{dim}f", blob))


def cosine(a: Iterable[float], b: Iterable[float]) -> float:
    av, bv = list(a), list(b)
    if len(av) != len(bv):
        return 0.0
    return float(sum(x * y for x, y in zip(av, bv)))


@dataclass(frozen=True)
class BackendStatus:
    backend: str
    dimension: int
    neural: bool
    local_only: bool
    model_path: str = ""
    detail: str = ""


def backend_status() -> dict[str, Any]:
    managed = model_status()
    if managed.get("ready"):
        return BackendStatus(
            "bge-small-zh-v1.5-fastembed", DEFAULT_MODEL_DIM, True, True, managed.get("cache_dir", ""),
            "Local BAAI/bge-small-zh-v1.5 ONNX model is ready through FastEmbed. Network access is disabled during retrieval.",
        ).__dict__ | {"model": managed}
    detail = "Dependency-free local vector fallback."
    if managed.get("installed") and not managed.get("runtime_available"):
        detail += " Neural model files are installed, but the FastEmbed runtime is unavailable."
    else:
        detail += " Install the optional BGE model pack for neural semantic retrieval."
    return BackendStatus(HASHING_BACKEND, DEFAULT_DIM, False, True, "", detail).__dict__ | {"model": managed}


def _fastembed_local(texts: list[str]) -> list[list[float]]:
    from fastembed import TextEmbedding  # type: ignore
    active = active_model_path()
    if active is None:
        raise RuntimeError("local neural model cache is not installed")
    key = str(active)
    model = _MODEL_CACHE.get(key)
    if model is None:
        # local_files_only is a hard guard: search must never fetch a model implicitly.
        model = TextEmbedding(model_name=DEFAULT_MODEL_ID, cache_dir=key, local_files_only=True)
        _MODEL_CACHE[key] = model
    rows = list(model.embed(texts))
    return [[float(v) for v in row] for row in rows]


def embed_many(texts: list[str]) -> tuple[str, list[list[float]]]:
    st = backend_status()
    if st["backend"] == "bge-small-zh-v1.5-fastembed":
        vecs = _fastembed_local(texts)
        return "bge-small-zh-v1.5-fastembed", vecs
    return HASHING_BACKEND, [hashing_embed(t) for t in texts]


def memory_document(card: dict[str, Any]) -> str:
    parts = [
        card.get("title", ""),
        card.get("summary", ""),
        " ".join(card.get("tags") or []),
        card.get("category", ""),
        card.get("content", ""),
    ]
    projects = card.get("projects") or []
    if projects:
        parts.extend((p.get("name", "") + " " + p.get("role", "")).strip() for p in projects)
    return "\n".join(x for x in parts if x)


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _ensure_table(db_path=None) -> None:
    init_db(db_path)
    with _connect(db_path) as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS memory_vectors(
                memory_id_fk INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                backend TEXT NOT NULL,
                dimension INTEGER NOT NULL,
                content_sha256 TEXT NOT NULL,
                vector_blob BLOB NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(memory_id_fk, backend)
            )"""
        )


def rebuild_vectors(*, memory_ids: list[str] | None = None, db_path=None) -> dict[str, Any]:
    """Build or refresh local vector cache. Safe to rerun; unchanged rows are skipped."""
    _ensure_table(db_path)
    with _connect(db_path) as con:
        params: list[Any] = []
        where = ""
        if memory_ids:
            mids = [m.upper() for m in memory_ids]
            where = " WHERE m.memory_id IN (%s)" % ",".join("?" for _ in mids)
            params.extend(mids)
        rows = con.execute(
            "SELECT m.* FROM memories m" + where + " ORDER BY m.id", params
        ).fetchall()
        cards = []
        for r in rows:
            tags = [x[0] for x in con.execute(
                "SELECT t.name FROM memory_tags mt JOIN tags t ON t.id=mt.tag_id WHERE mt.memory_id_fk=? ORDER BY t.name", (r["id"],)
            ).fetchall()]
            projs = [dict(x) for x in con.execute(
                "SELECT p.name,pm.role FROM project_memories pm JOIN projects p ON p.id=pm.project_id_fk WHERE pm.memory_id_fk=?", (r["id"],)
            ).fetchall()]
            d = dict(r); d["tags"] = tags; d["projects"] = projs
            cards.append((int(r["id"]), r["memory_id"], memory_document(d)))

        st = backend_status()
        backend = st["backend"]
        todo = []
        for rid, mid, doc in cards:
            h = content_hash(doc)
            cached = con.execute(
                "SELECT content_sha256 FROM memory_vectors WHERE memory_id_fk=? AND backend=?", (rid, backend)
            ).fetchone()
            if not cached or cached[0] != h:
                todo.append((rid, mid, doc, h))
        if not todo:
            return {"backend": backend, "updated": 0, "skipped": len(cards), "total": len(cards)}
        _, vecs = embed_many([x[2] for x in todo])
        for (rid, mid, doc, h), vec in zip(todo, vecs):
            con.execute(
                "INSERT OR REPLACE INTO memory_vectors(memory_id_fk,backend,dimension,content_sha256,vector_blob,updated_at) VALUES(?,?,?,?,?,?)",
                (rid, backend, len(vec), h, sqlite_blob(_pack(vec)), utc_now()),
            )
        return {"backend": backend, "updated": len(todo), "skipped": len(cards)-len(todo), "total": len(cards), "dimension": len(vecs[0]) if vecs else 0}


def sqlite_blob(data: bytes):
    # sqlite3.Binary kept behind a helper to keep import surface small.
    import sqlite3
    return sqlite3.Binary(data)


def vector_search(query: str, *, project_id: str | None = None, category: str | None = None, limit: int = 50,
                  include_archived: bool = False, db_path=None) -> list[dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        raise ValueError("search query is empty")
    _ensure_table(db_path)
    rebuild_vectors(db_path=db_path)
    st = backend_status(); backend = st["backend"]
    _, qvecs = embed_many([q]); qvec = qvecs[0]
    where = ["v.backend=?"]; params: list[Any] = [backend]
    if not include_archived: where.append("m.archived=0")
    if category and category != "all": where.append("m.category=?"); params.append(category)
    join = ""
    if project_id:
        join = " JOIN project_memories pm ON pm.memory_id_fk=m.id JOIN projects p ON p.id=pm.project_id_fk"
        where.append("p.project_id=?"); params.append(project_id.upper())
    sql = (
        "SELECT DISTINCT m.id,m.memory_id,m.title,m.summary,m.category,m.updated_at,m.pinned,m.favorite,v.dimension,v.vector_blob "
        "FROM memory_vectors v JOIN memories m ON m.id=v.memory_id_fk" + join +
        " WHERE " + " AND ".join(where)
    )
    hits = []
    with _connect(db_path) as con:
        for r in con.execute(sql, params).fetchall():
            try:
                score = cosine(qvec, _unpack(r["vector_blob"], int(r["dimension"])))
            except Exception:
                continue
            if score <= 0:
                continue
            hits.append({
                "memory_id": r["memory_id"], "title": r["title"], "summary": r["summary"], "category": r["category"],
                "updated_at": r["updated_at"], "pinned": bool(r["pinned"]), "favorite": bool(r["favorite"]),
                "vector_score": round(score, 6), "vector_backend": backend,
            })
    hits.sort(key=lambda x: (x["vector_score"], x["updated_at"]), reverse=True)
    return hits[:max(1, min(int(limit), 500))]
