from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .categories import CATEGORY_LABELS, infer_category, normalize_category

SCHEMA_VERSION = 8


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_home() -> Path:
    if os.environ.get("MEMORYBOX_HOME"):
        return Path(os.environ["MEMORYBOX_HOME"]).expanduser().resolve()
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "MemoryBox"
    return Path.home() / ".memorybox"


def default_db_path() -> Path:
    return default_home() / "memorybox.db"


def _connect(path: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
    p = Path(path) if path else default_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), timeout=20, factory=ClosingConnection)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=20000")
    con.execute("PRAGMA foreign_keys=ON")
    try:
        con.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError as exc:
        if "locked" not in str(exc).lower():
            con.close(); raise
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def init_db(path: str | os.PathLike[str] | None = None) -> Path:
    p = Path(path) if path else default_db_path()
    with _connect(p) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id TEXT UNIQUE,
            title TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            source_agent TEXT NOT NULL DEFAULT 'unknown',
            source_type TEXT NOT NULL DEFAULT 'conversation',
            source_uri TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            pinned INTEGER NOT NULL DEFAULT 0,
            favorite INTEGER NOT NULL DEFAULT 0,
            archived INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS tags(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE
        );
        CREATE TABLE IF NOT EXISTS memory_tags(
            memory_id_fk INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY(memory_id_fk, tag_id)
        );
        CREATE TABLE IF NOT EXISTS memory_versions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id_fk INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
            version_no INTEGER NOT NULL,
            snapshot_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(memory_id_fk, version_no)
        );
        CREATE TABLE IF NOT EXISTS agent_connections(
            agent_key TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            detected INTEGER NOT NULL DEFAULT 0,
            connected INTEGER NOT NULL DEFAULT 0,
            connection_mode TEXT NOT NULL DEFAULT '',
            config_path TEXT NOT NULL DEFAULT '',
            last_checked_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            memory_id TEXT,
            detail TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS transfer_origins(
            source_device_id TEXT NOT NULL,
            origin_memory_id TEXT NOT NULL,
            local_memory_id TEXT NOT NULL,
            transfer_id TEXT NOT NULL DEFAULT '',
            imported_at TEXT NOT NULL,
            PRIMARY KEY(source_device_id, origin_memory_id)
        );
        CREATE TABLE IF NOT EXISTS attachments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sha256 TEXT NOT NULL UNIQUE,
            original_name TEXT NOT NULL,
            mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
            size_bytes INTEGER NOT NULL,
            stored_relpath TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memory_attachments(
            memory_id_fk INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
            attachment_id INTEGER NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT 'attachment',
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            PRIMARY KEY(memory_id_fk, attachment_id)
        );
        CREATE TABLE IF NOT EXISTS sync_endpoints(
            endpoint_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            root_path TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            auto_import INTEGER NOT NULL DEFAULT 1,
            encryption_mode TEXT NOT NULL DEFAULT 'e2ee',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sync_receipts(
            endpoint_id TEXT NOT NULL,
            transfer_id TEXT NOT NULL,
            source_device_id TEXT NOT NULL,
            package_sha256 TEXT NOT NULL,
            status TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            processed_at TEXT NOT NULL,
            PRIMARY KEY(endpoint_id, transfer_id, source_device_id)
        );
        CREATE TABLE IF NOT EXISTS trusted_devices(
            endpoint_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            device_name TEXT NOT NULL DEFAULT '',
            public_key TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            trusted_at TEXT NOT NULL,
            revoked_at TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(endpoint_id, device_id)
        );
        CREATE TABLE IF NOT EXISTS recovery_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            fingerprint TEXT NOT NULL DEFAULT '',
            recovery_file_sha256 TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS insurance_settings(
            profile_id TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 0,
            endpoint_id TEXT NOT NULL DEFAULT '',
            interval_hours INTEGER NOT NULL DEFAULT 24,
            retention INTEGER NOT NULL DEFAULT 7,
            deep_verify INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS insurance_runs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            backup_path TEXT NOT NULL DEFAULT '',
            backup_sha256 TEXT NOT NULL DEFAULT '',
            transfer_id TEXT NOT NULL DEFAULT '',
            memory_count INTEGER NOT NULL DEFAULT 0,
            attachment_count INTEGER NOT NULL DEFAULT 0,
            detail TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        """)
        cols={r["name"] for r in con.execute("PRAGMA table_info(memories)").fetchall()}
        if "source_uri" not in cols:
            con.execute("ALTER TABLE memories ADD COLUMN source_uri TEXT NOT NULL DEFAULT ''")
        sync_cols={r["name"] for r in con.execute("PRAGMA table_info(sync_endpoints)").fetchall()}
        if "encryption_mode" not in sync_cols:
            # Existing v0.8 endpoints are preserved as plaintext until the user explicitly upgrades them.
            con.execute("ALTER TABLE sync_endpoints ADD COLUMN encryption_mode TEXT NOT NULL DEFAULT 'legacy-plaintext'")
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
        try:
            con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(memory_id,title,summary,content,category,content='memories',content_rowid='id')")
            con.executescript("""
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
              INSERT INTO memories_fts(rowid,memory_id,title,summary,content,category)
              VALUES(new.id,new.memory_id,new.title,new.summary,new.content,new.category);
            END;
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
              INSERT INTO memories_fts(memories_fts,rowid,memory_id,title,summary,content,category)
              VALUES('delete',old.id,old.memory_id,old.title,old.summary,old.content,old.category);
            END;
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
              INSERT INTO memories_fts(memories_fts,rowid,memory_id,title,summary,content,category)
              VALUES('delete',old.id,old.memory_id,old.title,old.summary,old.content,old.category);
              INSERT INTO memories_fts(rowid,memory_id,title,summary,content,category)
              VALUES(new.id,new.memory_id,new.title,new.summary,new.content,new.category);
            END;
            """)
            con.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
        except sqlite3.OperationalError:
            pass
    return p


def _compact_title(text: str, max_len: int = 48) -> str:
    first = next((x.strip() for x in re.split(r"[\r\n]+", text or "") if x.strip()), "未命名记忆")
    first = re.sub(r"\s+", " ", first)
    return first if len(first) <= max_len else first[: max_len - 1] + "…"


def _compact_summary(text: str, max_len: int = 180) -> str:
    one = re.sub(r"\s+", " ", (text or "").strip())
    return one if len(one) <= max_len else one[: max_len - 1] + "…"


def _next_memory_id(con: sqlite3.Connection) -> str:
    row = con.execute("SELECT MAX(CAST(SUBSTR(memory_id,2) AS INTEGER)) AS n FROM memories WHERE memory_id GLOB 'M[0-9]*'").fetchone()
    n = int(row["n"] or 0) + 1
    return f"M{n:06d}"


def _tags_for(con: sqlite3.Connection, row_id: int) -> list[str]:
    rows = con.execute("SELECT t.name FROM tags t JOIN memory_tags mt ON mt.tag_id=t.id WHERE mt.memory_id_fk=? ORDER BY t.name", (row_id,)).fetchall()
    return [r[0] for r in rows]


def _row_to_dict(con: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["tags"] = _tags_for(con, int(row["id"]))
    d["category_label"] = CATEGORY_LABELS.get(d["category"], d["category"])
    d["pinned"] = bool(d["pinned"])
    d["favorite"] = bool(d["favorite"])
    d["archived"] = bool(d["archived"])
    return d


def _set_tags(con: sqlite3.Connection, row_id: int, tags: Iterable[str]) -> None:
    for tag in sorted({t.strip() for t in tags if t and t.strip()}):
        con.execute("INSERT OR IGNORE INTO tags(name) VALUES(?)", (tag,))
        tid = con.execute("SELECT id FROM tags WHERE name=? COLLATE NOCASE", (tag,)).fetchone()[0]
        con.execute("INSERT OR IGNORE INTO memory_tags(memory_id_fk,tag_id) VALUES(?,?)", (row_id, tid))


def save_memory(content: str, *, title: str | None = None, summary: str | None = None, category: str = "auto", tags: Iterable[str] = (), source_agent: str = "unknown", source_uri: str = "", db_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    if not (content or "").strip():
        raise ValueError("memory content is empty")
    init_db(db_path)
    cat = infer_category(" ".join([title or "", summary or "", content])) if category in ("", "auto", None) else normalize_category(category)
    now = utc_now()
    with _connect(db_path) as con:
        # Serialize ID allocation so multiple agents can save concurrently without
        # producing the same stable Mxxxxxx identifier.
        con.execute("BEGIN IMMEDIATE")
        mid = _next_memory_id(con)
        cur = con.execute("INSERT INTO memories(memory_id,title,summary,content,category,source_agent,source_uri,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (
            mid, title or _compact_title(content), summary or _compact_summary(content), content.strip(), cat, source_agent or "unknown", source_uri or "", now, now
        ))
        row_id = cur.lastrowid
        _set_tags(con, int(row_id), tags)
        con.execute("INSERT INTO audit_log(action,memory_id,detail,created_at) VALUES('save',?,?,?)", (mid, cat, now))
        row = con.execute("SELECT * FROM memories WHERE id=?", (row_id,)).fetchone()
        return _row_to_dict(con, row)


def get_memory(memory_id: str, db_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    init_db(db_path)
    with _connect(db_path) as con:
        # Version-number allocation must also be serialized across concurrent agents.
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM memories WHERE memory_id=?", (memory_id.upper(),)).fetchone()
        if not row:
            raise KeyError(memory_id)
        result = _row_to_dict(con, row)
    from .attachments import list_attachments
    result["attachments"] = list_attachments(memory_id, db_path)
    return result


def list_memories(*, query: str | None = None, category: str | None = None, limit: int = 100, include_archived: bool = False, updated_after: str | None = None, updated_before: str | None = None, db_path: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    init_db(db_path)
    params: list[Any] = []
    where = []
    if not include_archived:
        where.append("m.archived=0")
    if category and category != "all":
        where.append("m.category=?")
        params.append(normalize_category(category))
    if updated_after:
        where.append("m.updated_at>=?")
        params.append(updated_after)
    if updated_before:
        where.append("m.updated_at<=?")
        params.append(updated_before)
    base_where = (" WHERE " + " AND ".join(where)) if where else ""
    with _connect(db_path) as con:
        rows = None
        if query:
            try:
                fts_where = ["memories_fts MATCH ?"]
                fparams: list[Any] = [query]
                if not include_archived:
                    fts_where.append("m.archived=0")
                if category and category != "all":
                    fts_where.append("m.category=?")
                    fparams.append(normalize_category(category))
                if updated_after:
                    fts_where.append("m.updated_at>=?")
                    fparams.append(updated_after)
                if updated_before:
                    fts_where.append("m.updated_at<=?")
                    fparams.append(updated_before)
                sql = "SELECT m.* FROM memories_fts JOIN memories m ON m.id=memories_fts.rowid WHERE " + " AND ".join(fts_where) + " ORDER BY m.pinned DESC,m.updated_at DESC LIMIT ?"
                fparams.append(limit)
                rows = con.execute(sql, fparams).fetchall()
            except sqlite3.OperationalError:
                rows = None
        if rows is None:
            qwhere = list(where)
            qparams = list(params)
            if query:
                like = f"%{query}%"
                qwhere.append("(m.memory_id LIKE ? OR m.title LIKE ? OR m.summary LIKE ? OR m.content LIKE ? OR EXISTS(SELECT 1 FROM memory_tags mt JOIN tags t ON t.id=mt.tag_id WHERE mt.memory_id_fk=m.id AND t.name LIKE ?))")
                qparams.extend([like] * 5)
            sql = "SELECT m.* FROM memories m" + ((" WHERE " + " AND ".join(qwhere)) if qwhere else "") + " ORDER BY m.pinned DESC,m.updated_at DESC LIMIT ?"
            qparams.append(limit)
            rows = con.execute(sql, qparams).fetchall()
        return [_row_to_dict(con, r) for r in rows]


def append_memory(memory_id: str, content: str, *, db_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    if not content.strip():
        raise ValueError("append content is empty")
    init_db(db_path)
    with _connect(db_path) as con:
        row = con.execute("SELECT * FROM memories WHERE memory_id=?", (memory_id.upper(),)).fetchone()
        if not row:
            raise KeyError(memory_id)
        snap = json.dumps(_row_to_dict(con, row), ensure_ascii=False)
        v = con.execute("SELECT COALESCE(MAX(version_no),0)+1 FROM memory_versions WHERE memory_id_fk=?", (row["id"],)).fetchone()[0]
        con.execute("INSERT INTO memory_versions(memory_id_fk,version_no,snapshot_json,created_at) VALUES(?,?,?,?)", (row["id"],v,snap,utc_now()))
        merged = row["content"].rstrip() + "\n\n---\n\n" + content.strip()
        now = utc_now()
        con.execute("UPDATE memories SET content=?,summary=?,updated_at=? WHERE id=?", (merged,_compact_summary(merged),now,row["id"]))
        con.execute("INSERT INTO audit_log(action,memory_id,detail,created_at) VALUES('append',?,?,?)", (memory_id.upper(), f"version {v}", now))
        new = con.execute("SELECT * FROM memories WHERE id=?", (row["id"],)).fetchone()
        return _row_to_dict(con,new)


def set_flag(memory_id: str, flag: str, value: bool, db_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    if flag not in {"pinned","favorite","archived"}:
        raise ValueError("invalid flag")
    init_db(db_path)
    with _connect(db_path) as con:
        con.execute(f"UPDATE memories SET {flag}=?,updated_at=? WHERE memory_id=?", (1 if value else 0, utc_now(), memory_id.upper()))
        row = con.execute("SELECT * FROM memories WHERE memory_id=?", (memory_id.upper(),)).fetchone()
        if not row:
            raise KeyError(memory_id)
        return _row_to_dict(con,row)


def category_counts(db_path: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    init_db(db_path)
    with _connect(db_path) as con:
        rows = con.execute("SELECT category,COUNT(*) AS n FROM memories WHERE archived=0 GROUP BY category ORDER BY n DESC,category").fetchall()
        return [{"category":r["category"],"label":CATEGORY_LABELS.get(r["category"],r["category"]),"count":r["n"]} for r in rows]


def related_memories(memory_id: str, limit: int = 8, db_path: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    base = get_memory(memory_id, db_path)
    tokens = [x for x in re.split(r"[^\w\u4e00-\u9fff]+", " ".join([base["title"],base["summary"]," ".join(base["tags"])])) if len(x) >= 2]
    query = " OR ".join(tokens[:8]) if tokens else base["category"]
    rows = list_memories(query=query, category=base["category"], limit=limit+1, db_path=db_path)
    return [x for x in rows if x["memory_id"] != memory_id][:limit]


def compose_context(memory_ids: list[str], db_path: str | os.PathLike[str] | None = None) -> str:
    cards = [get_memory(mid, db_path) for mid in memory_ids]
    out = ["# Memory Box Resume Context", "", "Use these memories as prior context. Verify mutable facts against the current workspace before acting.", ""]
    for c in cards:
        source = c.get('source_agent') or 'unknown'
        if c.get('source_uri'):
            source += f" · {c['source_uri']}"
        out.extend([f"## [{c['memory_id']}] {c['title']}", f"Category: {c['category_label']}", f"Source: {source}", f"Updated: {c['updated_at']}", f"Summary: {c['summary']}", "", c['content'], ""])
        attachments = c.get("attachments") or []
        if attachments:
            out.append("Attachments:")
            for a in attachments:
                note = f" — {a.get('note')}" if a.get('note') else ""
                out.append(f"- {a.get('original_name')} ({a.get('mime_type')}, {a.get('size_bytes')} bytes, sha256={a.get('sha256')}){note}")
                if a.get('local_path'):
                    out.append(f"  Local path: {a.get('local_path')}")
            out.append("")
    out.extend(["## Continuation rule", "Continue from the highest-priority unresolved action implied by these memories. Preserve recorded decisions unless current evidence contradicts them."])
    return "\n".join(out)


def import_uam_json(vault: str | os.PathLike[str], db_path: str | os.PathLike[str] | None = None) -> dict[str, int]:
    root = Path(vault).expanduser()
    cards = root / "memories"
    stats = {"imported":0,"skipped":0,"failed":0}
    if not cards.exists():
        return stats
    existing = {m["memory_id"] for m in list_memories(limit=100000, include_archived=True, db_path=db_path)}
    for path in sorted(cards.glob("M*.json")):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            mid = str(d.get("memory_id") or "")
            if mid in existing:
                stats["skipped"] += 1; continue
            content = d.get("narrative") or "\n".join(d.get("notes", [])) or d.get("summary", "")
            saved = save_memory(content, title=d.get("title"), summary=d.get("summary"), category=d.get("category","auto"), tags=d.get("tags",[]), source_agent=(d.get("source") or {}).get("agent","uam-v0.3"), db_path=db_path)
            # Keep old stable id if possible.
            with _connect(db_path) as con:
                if mid and re.fullmatch(r"M\d{6}",mid):
                    con.execute("UPDATE memories SET memory_id=? WHERE memory_id=?", (mid,saved["memory_id"]))
            stats["imported"] += 1
            existing.add(mid or saved["memory_id"])
        except Exception:
            stats["failed"] += 1
    return stats


def merge_memories(memory_ids: list[str], *, title: str | None = None, archive_sources: bool = False, db_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    if len(memory_ids) < 2:
        raise ValueError("merge requires at least two memory ids")
    cards = [get_memory(mid, db_path) for mid in memory_ids]
    cats = [c["category"] for c in cards]
    category = cats[0] if all(c == cats[0] for c in cats) else "auto"
    tags = sorted({t for c in cards for t in c["tags"]})
    body = []
    for c in cards:
        body.extend([f"## [{c['memory_id']}] {c['title']}", c["content"], ""])
    merged = save_memory("\n".join(body).strip(), title=title or "合并记忆：" + " / ".join(c["title"] for c in cards[:3]), category=category, tags=tags + ["merged"], source_agent="Memory Box merge", db_path=db_path)
    if archive_sources:
        for c in cards:
            set_flag(c["memory_id"], "archived", True, db_path)
    return merged

def bundle_by_query(query: str, *, category: str | None = None, limit: int = 10, db_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    cards = list_memories(query=query, category=category, limit=limit, db_path=db_path)
    ids = [c["memory_id"] for c in cards]
    return {"query": query, "memory_ids": ids, "count": len(ids), "context": compose_context(ids, db_path) if ids else ""}
