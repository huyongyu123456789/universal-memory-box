from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from .db import _connect, _row_to_dict, init_db, normalize_category


def _tokens(text: str) -> list[str]:
    text = (text or "").lower()
    latin = re.findall(r"[a-z0-9][a-z0-9_.+-]{1,}", text)
    cjk_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    cjk = []
    for chunk in cjk_chunks:
        cjk.append(chunk)
        if len(chunk) > 2:
            cjk.extend(chunk[i:i+2] for i in range(len(chunk)-1))
    out=[]
    seen=set()
    for t in latin+cjk:
        if t not in seen:
            seen.add(t); out.append(t)
    return out[:80]


def _age_days(ts: str) -> float:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds()/86400.0)
    except Exception:
        return 3650.0


def _field_score(q: str, qtokens: list[str], text: str, weight: float) -> float:
    low=(text or "").lower()
    if not low: return 0.0
    score = weight * (3.0 if q and q in low else 0.0)
    toks=set(_tokens(low))
    if qtokens:
        exact=sum(1 for t in qtokens if t in toks or t in low)
        score += weight * 1.15 * exact / max(1,len(qtokens))
        # Fuzzy title/summary matching helps recover from approximate wording without pretending to be an embedding model.
        if len(low) <= 500:
            ratio=SequenceMatcher(None,q[:180],low[:500]).ratio()
            if ratio>=0.45: score += weight * ratio * 0.8
    return score


def smart_search(query: str, *, project_id: str | None = None, category: str | None = None, limit: int = 20,
                 include_archived: bool = False, use_vector: bool = True, db_path=None) -> list[dict[str, Any]]:
    """Local hybrid ranking: lexical/metadata evidence + local vector similarity + recency/flags.

    v0.16 keeps all retrieval local. The default vector backend is dependency-free hashing; users may
    configure an existing local SentenceTransformer model directory for neural embeddings without
    sending data to a cloud service.
    """
    q=(query or "").strip().lower()
    if not q:
        raise ValueError("search query is empty")
    qtokens=_tokens(q)
    init_db(db_path)
    vector_map: dict[str, dict[str, Any]] = {}
    if use_vector:
        try:
            from .semantic import vector_search
            vector_hits = vector_search(q, project_id=project_id, category=category, limit=500, include_archived=include_archived, db_path=db_path)
            vector_map = {h["memory_id"]: h for h in vector_hits}
        except Exception:
            # Search remains usable even if an optional local embedding backend is unavailable/corrupt.
            vector_map = {}
    where=[]; params=[]
    if not include_archived: where.append("m.archived=0")
    if category and category!="all": where.append("m.category=?"); params.append(normalize_category(category))
    join=""
    if project_id:
        join=" JOIN project_memories pm ON pm.memory_id_fk=m.id JOIN projects p ON p.id=pm.project_id_fk"
        where.append("p.project_id=?"); params.append(project_id.upper())
    sql="SELECT DISTINCT m.* FROM memories m"+join+((" WHERE "+" AND ".join(where)) if where else "")+" ORDER BY m.updated_at DESC LIMIT 5000"
    with _connect(db_path) as con:
        rows=con.execute(sql,params).fetchall()
        project_map: dict[int,list[dict[str,str]]] = {}
        if rows:
            ids=[int(r["id"]) for r in rows]
            for i in range(0,len(ids),800):
                chunk=ids[i:i+800]
                ph=','.join('?'*len(chunk))
                for pr in con.execute(f"SELECT pm.memory_id_fk,p.project_id,p.name,p.status,pm.role FROM project_memories pm JOIN projects p ON p.id=pm.project_id_fk WHERE pm.memory_id_fk IN ({ph})",chunk).fetchall():
                    project_map.setdefault(int(pr['memory_id_fk']),[]).append({"project_id":pr['project_id'],"name":pr['name'],"status":pr['status'],"role":pr['role']})
        hits=[]
        for r in rows:
            d=_row_to_dict(con,r)
            tags=" ".join(d.get("tags") or [])
            projects=project_map.get(int(r["id"]),[])
            project_text=" ".join(p["name"] for p in projects)
            score=0.0; why=[]
            s_title=_field_score(q,qtokens,d.get("title", ""),5.0)
            s_summary=_field_score(q,qtokens,d.get("summary", ""),3.0)
            s_tags=_field_score(q,qtokens,tags,4.0)
            s_content=_field_score(q,qtokens,d.get("content", ""),1.2)
            s_project=_field_score(q,qtokens,project_text,4.5)
            lexical_score = s_title+s_summary+s_tags+s_content+s_project
            score += lexical_score
            vh = vector_map.get(d.get("memory_id", ""), {})
            vscore = float(vh.get("vector_score", 0.0) or 0.0)
            if vscore > 0:
                # Local vector evidence is additive, not authoritative; lexical/project evidence still matters.
                score += max(0.0, vscore) * 5.5
                if vscore >= 0.12: why.append("vector")
            if s_title>1: why.append("title")
            if s_summary>1: why.append("summary")
            if s_tags>1: why.append("tags")
            if s_project>1: why.append("project")
            if s_content>1: why.append("content")
            age=_age_days(d.get("updated_at", "")); recency=2.0*math.exp(-age/120.0); score+=recency
            if d.get("pinned"): score+=1.5; why.append("pinned")
            if d.get("favorite"): score+=0.7; why.append("favorite")
            if project_id: score+=1.0
            # Avoid ranking a row only because it is recent/pinned or due to tiny hashing collisions.
            if lexical_score <= 0 and vscore < 0.16:
                continue
            d["projects"]=projects
            d["vector_score"]=round(vscore,6)
            d["vector_backend"]=vh.get("vector_backend", "")
            d["retrieval_score"]=round(score,4)
            d["retrieval_reasons"]=why[:7]
            hits.append(d)
    hits.sort(key=lambda x:(x["retrieval_score"],x.get("updated_at", "")), reverse=True)
    return hits[:max(1,min(int(limit),200))]
