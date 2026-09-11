from __future__ import annotations

from typing import Any

from .db import _connect, compose_context, get_memory, init_db, utc_now

PROJECT_STATUSES = {"active", "paused", "completed", "archived"}


def _next_project_id(con) -> str:
    rows = con.execute("SELECT project_id FROM projects WHERE project_id GLOB 'P[0-9][0-9][0-9][0-9][0-9][0-9]' ORDER BY project_id DESC LIMIT 1").fetchone()
    n = int(rows[0][1:]) + 1 if rows else 1
    return f"P{n:06d}"


def _normalize_status(status: str) -> str:
    s = (status or "active").strip().lower()
    if s not in PROJECT_STATUSES:
        raise ValueError(f"invalid project status: {status}")
    return s


def _project_row(con, row) -> dict[str, Any]:
    d = dict(row)
    d["archived"] = bool(d.get("archived"))
    counts = con.execute(
        "SELECT COUNT(*) AS n, MAX(m.updated_at) AS latest FROM project_memories pm JOIN memories m ON m.id=pm.memory_id_fk WHERE pm.project_id_fk=?",
        (row["id"],),
    ).fetchone()
    d["memory_count"] = int(counts["n"] or 0)
    d["latest_memory_at"] = counts["latest"] or ""
    return d


def create_project(name: str, *, summary: str = "", current_state: str = "", next_action: str = "", status: str = "active", db_path=None) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValueError("project name is empty")
    if len(name) > 160:
        raise ValueError("project name is too long")
    init_db(db_path)
    now = utc_now()
    with _connect(db_path) as con:
        con.execute("BEGIN IMMEDIATE")
        pid = _next_project_id(con)
        cur = con.execute(
            "INSERT INTO projects(project_id,name,summary,current_state,next_action,status,created_at,updated_at,archived) VALUES(?,?,?,?,?,?,?,?,0)",
            (pid, name, summary.strip(), current_state.strip(), next_action.strip(), _normalize_status(status), now, now),
        )
        row = con.execute("SELECT * FROM projects WHERE id=?", (cur.lastrowid,)).fetchone()
        return _project_row(con, row)


def list_projects(*, include_archived: bool = False, status: str | None = None, limit: int = 500, db_path=None) -> list[dict[str, Any]]:
    init_db(db_path)
    where = []
    params: list[Any] = []
    if not include_archived:
        where.append("p.archived=0")
    if status and status != "all":
        where.append("p.status=?")
        params.append(_normalize_status(status))
    sql = "SELECT p.* FROM projects p" + ((" WHERE " + " AND ".join(where)) if where else "") + " ORDER BY CASE p.status WHEN 'active' THEN 0 WHEN 'paused' THEN 1 WHEN 'completed' THEN 2 ELSE 3 END, p.updated_at DESC LIMIT ?"
    params.append(max(1, min(int(limit), 5000)))
    with _connect(db_path) as con:
        return [_project_row(con, r) for r in con.execute(sql, params).fetchall()]


def get_project(project_id: str, *, include_memories: bool = True, memory_limit: int = 200, db_path=None) -> dict[str, Any]:
    init_db(db_path)
    pid = (project_id or "").upper()
    with _connect(db_path) as con:
        row = con.execute("SELECT * FROM projects WHERE project_id=?", (pid,)).fetchone()
        if not row:
            raise KeyError(project_id)
        result = _project_row(con, row)
        if include_memories:
            rows = con.execute(
                """
                SELECT m.*, pm.role AS project_role, pm.added_at AS project_added_at
                FROM project_memories pm JOIN memories m ON m.id=pm.memory_id_fk
                WHERE pm.project_id_fk=?
                ORDER BY m.pinned DESC, m.favorite DESC, m.updated_at DESC
                LIMIT ?
                """,
                (row["id"], max(1, min(int(memory_limit), 5000))),
            ).fetchall()
            result["memories"] = [
                {
                    "memory_id": r["memory_id"], "title": r["title"], "summary": r["summary"], "category": r["category"],
                    "updated_at": r["updated_at"], "pinned": bool(r["pinned"]), "favorite": bool(r["favorite"]),
                    "role": r["project_role"], "added_at": r["project_added_at"],
                }
                for r in rows
            ]
        return result


def update_project(project_id: str, *, name: str | None = None, summary: str | None = None, current_state: str | None = None,
                   next_action: str | None = None, status: str | None = None, archived: bool | None = None, db_path=None) -> dict[str, Any]:
    init_db(db_path)
    pid = (project_id or "").upper()
    fields = []
    params: list[Any] = []
    if name is not None:
        if not name.strip(): raise ValueError("project name is empty")
        fields.append("name=?"); params.append(name.strip())
    if summary is not None: fields.append("summary=?"); params.append(summary.strip())
    if current_state is not None: fields.append("current_state=?"); params.append(current_state.strip())
    if next_action is not None: fields.append("next_action=?"); params.append(next_action.strip())
    if status is not None: fields.append("status=?"); params.append(_normalize_status(status))
    if archived is not None: fields.append("archived=?"); params.append(1 if archived else 0)
    if not fields:
        return get_project(pid, db_path=db_path)
    fields.append("updated_at=?"); params.append(utc_now()); params.append(pid)
    with _connect(db_path) as con:
        con.execute("UPDATE projects SET " + ",".join(fields) + " WHERE project_id=?", params)
        if con.execute("SELECT changes()").fetchone()[0] == 0:
            raise KeyError(project_id)
    return get_project(pid, db_path=db_path)


def add_memory_to_project(project_id: str, memory_id: str, *, role: str = "context", db_path=None) -> dict[str, Any]:
    init_db(db_path)
    pid, mid = (project_id or "").upper(), (memory_id or "").upper()
    role = (role or "context").strip()[:48]
    with _connect(db_path) as con:
        con.execute("BEGIN IMMEDIATE")
        p = con.execute("SELECT id FROM projects WHERE project_id=?", (pid,)).fetchone()
        m = con.execute("SELECT id FROM memories WHERE memory_id=?", (mid,)).fetchone()
        if not p: raise KeyError(project_id)
        if not m: raise KeyError(memory_id)
        con.execute("INSERT OR REPLACE INTO project_memories(project_id_fk,memory_id_fk,role,added_at) VALUES(?,?,?,?)", (p["id"], m["id"], role, utc_now()))
        con.execute("UPDATE projects SET updated_at=? WHERE id=?", (utc_now(), p["id"]))
    refresh_project_insights(pid, db_path=db_path)
    return get_project(pid, db_path=db_path)


def remove_memory_from_project(project_id: str, memory_id: str, *, db_path=None) -> dict[str, Any]:
    init_db(db_path)
    pid, mid = (project_id or "").upper(), (memory_id or "").upper()
    with _connect(db_path) as con:
        p = con.execute("SELECT id FROM projects WHERE project_id=?", (pid,)).fetchone()
        m = con.execute("SELECT id FROM memories WHERE memory_id=?", (mid,)).fetchone()
        if not p: raise KeyError(project_id)
        if not m: raise KeyError(memory_id)
        con.execute("DELETE FROM project_memories WHERE project_id_fk=? AND memory_id_fk=?", (p["id"], m["id"]))
        con.execute("UPDATE projects SET updated_at=? WHERE id=?", (utc_now(), p["id"]))
    refresh_project_insights(pid, db_path=db_path)
    return get_project(pid, db_path=db_path)


def projects_for_memory(memory_id: str, *, db_path=None) -> list[dict[str, Any]]:
    init_db(db_path)
    mid = (memory_id or "").upper()
    with _connect(db_path) as con:
        rows = con.execute(
            """SELECT p.project_id,p.name,p.status,pm.role FROM project_memories pm
               JOIN projects p ON p.id=pm.project_id_fk JOIN memories m ON m.id=pm.memory_id_fk
               WHERE m.memory_id=? ORDER BY p.updated_at DESC""",
            (mid,),
        ).fetchall()
        return [dict(r) for r in rows]


def project_resume(project_id: str, *, query: str = "", limit: int = 12, db_path=None) -> dict[str, Any]:
    from .retrieval import smart_search
    refresh_project_insights(project_id, db_path=db_path)
    project = get_project(project_id, include_memories=False, db_path=db_path)
    effective_summary = project.get("summary") or project.get("auto_summary", "")
    effective_state = project.get("current_state") or project.get("auto_current_state", "")
    effective_next = project.get("next_action") or project.get("auto_next_action", "")
    search_query = (query or "").strip() or " ".join(x for x in [project["name"], effective_summary, effective_state, effective_next] if x)
    hits = smart_search(search_query, project_id=project["project_id"], limit=limit, db_path=db_path)
    ids = [h["memory_id"] for h in hits]
    header = [
        "# Memory Box Project Resume", "",
        f"Project: [{project['project_id']}] {project['name']}",
        f"Status: {project['status']}",
        f"Summary: {effective_summary or '(not set)'}",
        f"Current state: {effective_state or '(not set)'}",
        f"Next action: {effective_next or '(not set)'}", "",
    ]
    context = "\n".join(header)
    if ids:
        context += compose_context(ids, db_path).replace("# Memory Box Resume Context", "## Ranked project memories", 1)
    else:
        context += "No linked memories yet."
    return {"project": project, "query": search_query, "memory_ids": ids, "hits": hits, "context": context}


def suggest_project_memories(project_id: str, *, limit: int = 12, db_path=None) -> list[dict[str, Any]]:
    from .retrieval import smart_search
    project = get_project(project_id, include_memories=False, db_path=db_path)
    query = " ".join(x for x in [project["name"], project.get("summary", ""), project.get("current_state", ""), project.get("next_action", "")] if x)
    hits = smart_search(query, limit=max(limit * 3, 30), db_path=db_path)
    linked = {m["memory_id"] for m in get_project(project_id, db_path=db_path).get("memories", [])}
    return [h for h in hits if h["memory_id"] not in linked][:max(1, min(int(limit), 50))]


def derive_project_insights(project_id: str, *, memory_limit: int = 40, db_path=None) -> dict[str, Any]:
    """Build a deterministic local project digest without overwriting curated fields."""
    project = get_project(project_id, include_memories=True, memory_limit=memory_limit, db_path=db_path)
    memories = project.get("memories", [])
    if not memories:
        return {
            "project_id": project["project_id"], "auto_summary": "", "auto_current_state": "", "auto_next_action": "",
            "memory_count": 0, "basis_memory_ids": [], "generated_at": utc_now(),
        }

    def clean(s: str) -> str:
        return " ".join((s or "").split()).strip()

    def snippet(m: dict[str, Any]) -> str:
        return clean(m.get("summary") or m.get("title") or "")[:280]

    basis = [m["memory_id"] for m in memories[:12]]
    role_groups: dict[str, list[dict[str, Any]]] = {}
    for m in memories:
        role_groups.setdefault((m.get("role") or "context").lower(), []).append(m)

    summary_items = []
    for m in memories:
        s = snippet(m)
        if s and s not in summary_items:
            summary_items.append(s)
        if len(summary_items) >= 3:
            break
    auto_summary = "；".join(summary_items)

    state_candidates = []
    for role in ("decision", "evidence", "context", "merged"):
        for m in role_groups.get(role, []):
            s = snippet(m)
            if s and s not in state_candidates:
                state_candidates.append(s)
            if len(state_candidates) >= 3:
                break
        if len(state_candidates) >= 3:
            break
    if not state_candidates:
        state_candidates = summary_items[:2]
    auto_current_state = "；".join(state_candidates[:3])

    next_candidates = []
    for role, group in role_groups.items():
        if "next" in role or "todo" in role or "action" in role:
            for m in group:
                s = snippet(m)
                if s and s not in next_candidates:
                    next_candidates.append(s)
    if not next_candidates:
        # Conservative extraction: only explicit action language from recent summaries/titles.
        action_markers = ("next", "todo", "follow-up", "下一步", "待办", "继续", "需要", "计划")
        for m in memories:
            s = snippet(m)
            if any(mark in s.lower() for mark in action_markers):
                next_candidates.append(s)
                break
    auto_next_action = next_candidates[0] if next_candidates else ""
    return {
        "project_id": project["project_id"], "auto_summary": auto_summary[:1200], "auto_current_state": auto_current_state[:1200],
        "auto_next_action": auto_next_action[:800], "memory_count": len(memories), "basis_memory_ids": basis, "generated_at": utc_now(),
    }


def refresh_project_insights(project_id: str, *, db_path=None) -> dict[str, Any]:
    """Refresh derived project fields only. User-authored summary/state/next_action are never overwritten."""
    insight = derive_project_insights(project_id, db_path=db_path)
    with _connect(db_path) as con:
        con.execute(
            "UPDATE projects SET auto_summary=?,auto_current_state=?,auto_next_action=?,auto_updated_at=? WHERE project_id=?",
            (insight["auto_summary"], insight["auto_current_state"], insight["auto_next_action"], insight["generated_at"], insight["project_id"]),
        )
    return get_project(insight["project_id"], db_path=db_path)
