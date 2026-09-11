from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from typing import Any

from .db import _connect, get_memory, init_db, merge_memories, utc_now
from .projects import add_memory_to_project, projects_for_memory
from .semantic import vector_search


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _tokens(text: str) -> set[str]:
    t = _norm(text)
    out = set(re.findall(r"[a-z0-9][a-z0-9_.+\-/]{1,}", t))
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", t):
        out.update(chunk[i:i+2] for i in range(len(chunk)-1))
    return out


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def duplicate_score(a: dict[str, Any], b: dict[str, Any], *, vector_score: float = 0.0) -> dict[str, Any]:
    ac, bc = _norm(a.get("content", "")), _norm(b.get("content", ""))
    exact = bool(ac and bc and hashlib.sha256(ac.encode()).digest() == hashlib.sha256(bc.encode()).digest())
    title = SequenceMatcher(None, _norm(a.get("title", ""))[:240], _norm(b.get("title", ""))[:240]).ratio()
    summary = SequenceMatcher(None, _norm(a.get("summary", ""))[:500], _norm(b.get("summary", ""))[:500]).ratio()
    overlap = _jaccard(_tokens(" ".join([a.get("title", ""), a.get("summary", ""), ac[:6000]])), _tokens(" ".join([b.get("title", ""), b.get("summary", ""), bc[:6000]])))
    if exact:
        score = 1.0
        reason = "exact-content"
    else:
        score = 0.42 * max(0.0, vector_score) + 0.26 * overlap + 0.18 * title + 0.14 * summary
        reason = "near-duplicate"
    return {
        "score": round(min(1.0, score), 6),
        "vector_score": round(vector_score, 6),
        "token_overlap": round(overlap, 6),
        "title_similarity": round(title, 6),
        "summary_similarity": round(summary, 6),
        "exact": exact,
        "reason": reason,
    }


def find_duplicates(memory_id: str, *, limit: int = 12, threshold: float = 0.72, db_path=None) -> list[dict[str, Any]]:
    """Return duplicate candidates. This never merges or archives automatically."""
    source = get_memory(memory_id, db_path)
    query = "\n".join([source.get("title", ""), source.get("summary", ""), source.get("content", "")[:8000]])
    candidates = vector_search(query, limit=max(30, int(limit) * 5), include_archived=False, db_path=db_path)
    out = []
    for cand in candidates:
        if cand["memory_id"] == source["memory_id"]:
            continue
        target = get_memory(cand["memory_id"], db_path)
        scores = duplicate_score(source, target, vector_score=float(cand.get("vector_score", 0.0)))
        # Exact content is always surfaced; near duplicates must clear the requested threshold.
        if not scores["exact"] and scores["score"] < threshold:
            continue
        out.append({
            "memory_id": target["memory_id"],
            "title": target["title"],
            "summary": target["summary"],
            "updated_at": target["updated_at"],
            "category": target["category"],
            **scores,
        })
    out.sort(key=lambda x: (x["score"], x["updated_at"]), reverse=True)
    return out[:max(1, min(int(limit), 100))]


def scan_duplicates(*, limit: int = 100, threshold: float = 0.78, db_path=None) -> list[dict[str, Any]]:
    """Scan active memories and return de-duplicated candidate pairs."""
    init_db(db_path)
    with _connect(db_path) as con:
        mids = [r[0] for r in con.execute("SELECT memory_id FROM memories WHERE archived=0 ORDER BY updated_at DESC LIMIT ?", (max(2, min(int(limit), 1000)),)).fetchall()]
    seen: set[tuple[str, str]] = set()
    pairs = []
    for mid in mids:
        for d in find_duplicates(mid, limit=8, threshold=threshold, db_path=db_path):
            key = tuple(sorted((mid, d["memory_id"])))
            if key in seen:
                continue
            seen.add(key)
            pairs.append({"memory_ids": list(key), **d})
    pairs.sort(key=lambda x: x["score"], reverse=True)
    return pairs


def merge_duplicate_memories(memory_ids: list[str], *, title: str | None = None, archive_sources: bool = True, db_path=None) -> dict[str, Any]:
    """Explicitly merge reviewed duplicate memories and preserve their project membership."""
    mids = []
    for mid in memory_ids:
        u = (mid or "").upper()
        if u and u not in mids:
            mids.append(u)
    if len(mids) < 2:
        raise ValueError("merge requires at least two unique memory ids")
    project_roles: dict[str, set[str]] = {}
    for mid in mids:
        get_memory(mid, db_path)  # validate before mutating anything
        for p in projects_for_memory(mid, db_path=db_path):
            project_roles.setdefault(p["project_id"], set()).add(p.get("role") or "context")
    merged = merge_memories(mids, title=title, archive_sources=archive_sources, db_path=db_path)
    for pid, roles in project_roles.items():
        role = next(iter(roles)) if len(roles) == 1 else "merged"
        add_memory_to_project(pid, merged["memory_id"], role=role, db_path=db_path)
    with _connect(db_path) as con:
        con.execute(
            "INSERT INTO dedup_events(action,source_ids,result_memory_id,detail,created_at) VALUES(?,?,?,?,?)",
            ("merge", json.dumps(mids, ensure_ascii=False), merged["memory_id"], json.dumps({"archive_sources": archive_sources, "projects": sorted(project_roles)}, ensure_ascii=False), utc_now()),
        )
    merged["merged_from"] = mids
    merged["projects_preserved"] = sorted(project_roles)
    return merged
