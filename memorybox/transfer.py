from __future__ import annotations

import hashlib
import html
import json
import os
import re
import uuid
import webbrowser
import zipfile
from pathlib import Path
from typing import Any, Iterable

from . import __version__
from .attachments import add_attachment_bytes, attachment_root, list_attachments
from .db import (
    _connect,
    _next_memory_id,
    _row_to_dict,
    _set_tags,
    compose_context,
    default_home,
    get_memory,
    init_db,
    list_memories,
    utc_now,
)

TRANSFER_FORMAT = "memorybox-transfer"
TRANSFER_VERSION = 2
SUPPORTED_TRANSFER_VERSIONS = {1, 2}
MAX_PACKAGE_BYTES = int(os.environ.get("MEMORYBOX_MAX_PACKAGE_BYTES", str(2 * 1024 * 1024 * 1024)))
MAX_ENTRY_BYTES = int(os.environ.get("MEMORYBOX_MAX_ENTRY_BYTES", str(1024 * 1024 * 1024)))
MAX_MEMORIES = 100_000
MAX_ATTACHMENTS = 100_000
_ROOT_FILES = {"manifest.json", "memories.json", "resume.md", "viewer.html", "README.txt"}
_ATTACH_INDEX = "attachments/index.json"
_BLOB_RE = re.compile(r"^attachments/blobs/([0-9a-f]{64})$")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _ensure_transfer_schema(db_path=None) -> str:
    init_db(db_path)
    with _connect(db_path) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS transfer_origins(
            source_device_id TEXT NOT NULL,
            origin_memory_id TEXT NOT NULL,
            local_memory_id TEXT NOT NULL,
            transfer_id TEXT NOT NULL DEFAULT '',
            imported_at TEXT NOT NULL,
            PRIMARY KEY(source_device_id, origin_memory_id)
        )
        """)
        row = con.execute("SELECT value FROM meta WHERE key='device_id'").fetchone()
        if row and row[0]:
            return str(row[0])
        did = str(uuid.uuid4())
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('device_id',?)", (did,))
        return did


def device_id(db_path=None) -> str:
    return _ensure_transfer_schema(db_path)


def _runtime_home(db_path=None) -> Path:
    return default_home() if db_path is None else Path(db_path).expanduser().resolve().parent


def _versions_for(memory_id: str, db_path=None) -> list[dict[str, Any]]:
    with _connect(db_path) as con:
        row = con.execute("SELECT id FROM memories WHERE memory_id=?", (memory_id.upper(),)).fetchone()
        if not row:
            return []
        out = []
        for v in con.execute(
            "SELECT version_no,snapshot_json,created_at FROM memory_versions WHERE memory_id_fk=? ORDER BY version_no",
            (row["id"],),
        ).fetchall():
            try:
                snapshot = json.loads(v["snapshot_json"])
            except Exception:
                snapshot = {"raw_snapshot": v["snapshot_json"]}
            out.append({"version_no": int(v["version_no"]), "created_at": v["created_at"], "snapshot": snapshot})
        return out


def _card_for_export(card: dict[str, Any], db_path=None) -> dict[str, Any]:
    keys = [
        "memory_id", "title", "summary", "content", "category", "source_agent", "source_type", "source_uri",
        "created_at", "updated_at", "pinned", "favorite", "archived", "tags",
    ]
    out = {k: card.get(k) for k in keys}
    out["versions"] = _versions_for(card["memory_id"], db_path)
    return out


def _select_cards(*, memory_ids: Iterable[str] | None = None, query: str | None = None,
                  category: str | None = None, include_archived: bool = True, db_path=None) -> list[dict[str, Any]]:
    if memory_ids:
        cards = [get_memory(mid, db_path) for mid in memory_ids]
    else:
        cards = list_memories(query=query, category=category, limit=MAX_MEMORIES,
                              include_archived=include_archived, db_path=db_path)
    if len(cards) > MAX_MEMORIES:
        raise ValueError("too many memories for one transfer package")
    return cards


def _attachment_catalog(cards: list[dict[str, Any]], db_path=None) -> list[dict[str, Any]]:
    by_hash: dict[str, dict[str, Any]] = {}
    for c in cards:
        for a in list_attachments(c["memory_id"], db_path):
            sha = a["sha256"]
            item = by_hash.setdefault(sha, {
                "sha256": sha,
                "original_name": a["original_name"],
                "mime_type": a["mime_type"],
                "size_bytes": int(a["size_bytes"]),
                "package_path": f"attachments/blobs/{sha}",
                "links": [],
            })
            item["links"].append({
                "memory_id": c["memory_id"],
                "role": a.get("role") or "attachment",
                "note": a.get("note") or "",
            })
    if len(by_hash) > MAX_ATTACHMENTS:
        raise ValueError("too many attachments for one transfer package")
    return list(by_hash.values())


def _viewer_html(cards: list[dict[str, Any]], manifest: dict[str, Any], attachments: list[dict[str, Any]]) -> str:
    links_by_memory: dict[str, list[dict[str, Any]]] = {}
    for a in attachments:
        for link in a.get("links") or []:
            links_by_memory.setdefault(str(link.get("memory_id")), []).append({**a, **link})
    chunks = []
    for c in cards:
        tags = " ".join(f"<span class='tag'>{html.escape(str(t))}</span>" for t in c.get("tags", []))
        src = html.escape(str(c.get("source_agent") or "unknown"))
        uri = str(c.get("source_uri") or "")
        if uri:
            src += " · " + html.escape(uri)
        att_html = ""
        atts = links_by_memory.get(str(c.get("memory_id")), [])
        if atts:
            rows = []
            for a in atts:
                name = html.escape(str(a.get("original_name") or "attachment"))
                href = html.escape(str(a.get("package_path") or ""), quote=True)
                mime = html.escape(str(a.get("mime_type") or "application/octet-stream"))
                note = html.escape(str(a.get("note") or ""))
                rows.append(f"<li><a href='{href}' download='{name}'>{name}</a> · {mime} · {int(a.get('size_bytes') or 0)} bytes{(' · '+note) if note else ''}</li>")
            att_html = "<h3>Attachments</h3><ul>" + "".join(rows) + "</ul>"
        chunks.append(f"""
<section class="card">
  <div class="meta">{html.escape(str(c.get('memory_id')))} · {html.escape(str(c.get('category')))} · {html.escape(str(c.get('updated_at')))}</div>
  <h2>{html.escape(str(c.get('title') or ''))}</h2>
  <div class="source">来源：{src}</div>
  <p class="summary">{html.escape(str(c.get('summary') or ''))}</p>
  <div>{tags}</div>
  <pre>{html.escape(str(c.get('content') or ''))}</pre>
  {att_html}
</section>""")
    return f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Memory Box Replay</title><style>body{{font-family:system-ui,'Microsoft YaHei',sans-serif;max-width:980px;margin:auto;padding:28px;background:#f5f5f3;color:#191919}}h1{{margin-bottom:4px}}.lead,.meta,.source{{color:#666;font-size:13px}}.card{{background:white;border:1px solid #deded8;border-radius:14px;padding:18px;margin:14px 0}}pre{{white-space:pre-wrap;word-break:break-word;background:#f7f7f4;padding:14px;border-radius:10px;line-height:1.55}}.tag{{display:inline-block;padding:3px 8px;margin:2px;background:#eee;border-radius:999px;font-size:12px}}.summary{{line-height:1.6}}a{{color:#1b5fbf}}</style></head><body>
<h1>🧠 Memory Box Replay</h1><p class='lead'>Transfer {html.escape(manifest['transfer_id'])} · {len(cards)} 条记忆 · {len(attachments)} 个附件 · 生成于 {html.escape(manifest['created_at'])}</p>
{''.join(chunks)}
</body></html>"""


def _readme_text(manifest: dict[str, Any]) -> str:
    return (
        "Memory Box Complete Session Capsule\n"
        "==================================\n\n"
        f"Transfer ID: {manifest['transfer_id']}\n"
        f"Created: {manifest['created_at']}\n"
        f"Memories: {manifest['memory_count']}\n"
        f"Attachments: {manifest.get('attachment_count', 0)}\n\n"
        "This .mboxpack file is a ZIP-compatible, data-only package.\n"
        "It may contain the original PDF, Word, image, code, CSV and other files attached to saved memories.\n"
        "On a computer with Memory Box installed, double-click it or use:\n"
        "  memorybox import-pack <file.mboxpack> --open\n\n"
        "viewer.html is an offline replay view. resume.md is a portable AI continuation context.\n"
        "Absolute source paths are not exported. Attachments are addressed by SHA-256 and restored into the destination Memory Box store.\n"
        "The package may contain sensitive information. Treat it like a private document.\n"
    )


def _portable_context(cards: list[dict[str, Any]], attachments: list[dict[str, Any]]) -> str:
    links: dict[str, list[dict[str, Any]]] = {}
    for a in attachments:
        for link in a.get("links") or []:
            links.setdefault(str(link.get("memory_id")), []).append({**a, **link})
    out = ["# Memory Box Resume Context", "", "Portable session capsule. Verify mutable facts against the destination workspace before acting.", ""]
    for c in cards:
        source = c.get("source_agent") or "unknown"
        if c.get("source_uri"):
            source += f" · {c['source_uri']}"
        out.extend([f"## [{c['memory_id']}] {c['title']}", f"Category: {c.get('category')}", f"Source: {source}", f"Updated: {c.get('updated_at')}", f"Summary: {c.get('summary') or ''}", "", str(c.get("content") or ""), ""])
        atts = links.get(str(c.get("memory_id")), [])
        if atts:
            out.append("Attachments carried in this capsule:")
            for a in atts:
                note = f" — {a.get('note')}" if a.get("note") else ""
                out.append(f"- {a.get('original_name')} ({a.get('mime_type')}, {a.get('size_bytes')} bytes, sha256={a.get('sha256')}){note}")
            out.append("")
    out.extend(["## Continuation rule", "Continue from the highest-priority unresolved action implied by these memories. Preserve recorded decisions unless current evidence contradicts them. Use the restored local attachments when needed."])
    return "\n".join(out)


def export_transfer_bundle(output: str | os.PathLike[str], *, memory_ids: Iterable[str] | None = None,
                           query: str | None = None, category: str | None = None,
                           as_folder: bool = False, include_archived: bool = True, db_path=None) -> dict[str, Any]:
    _ensure_transfer_schema(db_path)
    cards = [_card_for_export(c, db_path) for c in _select_cards(
        memory_ids=memory_ids, query=query, category=category, include_archived=include_archived, db_path=db_path)]
    attachments = _attachment_catalog(cards, db_path)
    transfer_id = str(uuid.uuid4())
    memories_b = _json_bytes({"memories": cards})
    attachments_b = _json_bytes({"attachments": attachments})
    resume_b = _portable_context(cards, attachments).encode("utf-8")
    manifest = {
        "format": TRANSFER_FORMAT,
        "format_version": TRANSFER_VERSION,
        "transfer_id": transfer_id,
        "created_at": utc_now(),
        "memorybox_version": __version__,
        "source_device_id": device_id(db_path),
        "memory_count": len(cards),
        "attachment_count": len(attachments),
        "attachment_bytes": sum(int(a["size_bytes"]) for a in attachments),
        "scope": {"memory_ids": list(memory_ids or []), "query": query or "", "category": category or "", "include_archived": bool(include_archived)},
        "checksums": {},
    }
    viewer_b = _viewer_html(cards, manifest, attachments).encode("utf-8")
    readme_b = _readme_text(manifest).encode("utf-8")
    data_files: dict[str, bytes] = {
        "memories.json": memories_b,
        _ATTACH_INDEX: attachments_b,
        "resume.md": resume_b,
        "viewer.html": viewer_b,
        "README.txt": readme_b,
    }
    root = attachment_root(db_path)
    blob_paths: dict[str, Path] = {}
    for a in attachments:
        fp = root / str(a["sha256"])[:2] / str(a["sha256"])
        if not fp.is_file():
            raise FileNotFoundError(f"managed attachment missing: {a['original_name']}")
        if fp.stat().st_size != int(a["size_bytes"]) or _sha256_file(fp) != a["sha256"]:
            raise ValueError(f"managed attachment failed integrity check: {a['original_name']}")
        blob_paths[a["package_path"]] = fp
    checksums = {name: _sha256(data) for name, data in data_files.items()}
    checksums.update({name: _sha256_file(fp) for name, fp in blob_paths.items()})
    manifest["checksums"] = checksums
    manifest_b = _json_bytes(manifest)
    estimated_total = len(manifest_b) + sum(len(x) for x in data_files.values()) + sum(fp.stat().st_size for fp in blob_paths.values())
    if estimated_total > MAX_PACKAGE_BYTES:
        raise ValueError("complete session exceeds configured package size limit")

    out = Path(output).expanduser()
    if as_folder or out.suffix == "":
        out.mkdir(parents=True, exist_ok=True)
        for name, data in {"manifest.json": manifest_b, **data_files}.items():
            fp = out / name
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_bytes(data)
        for name, src in blob_paths.items():
            fp = out / name
            fp.parent.mkdir(parents=True, exist_ok=True)
            if not fp.exists():
                fp.write_bytes(src.read_bytes())
        kind = "folder"
    else:
        if out.suffix.lower() != ".mboxpack":
            out = out.with_suffix(out.suffix + ".mboxpack" if out.suffix else ".mboxpack")
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as zf:
            zf.writestr("manifest.json", manifest_b)
            for name, data in data_files.items():
                zf.writestr(name, data)
            for name, src in blob_paths.items():
                zf.write(src, arcname=name)
        kind = "mboxpack"
    return {"ok": True, "path": str(out.resolve()), "kind": kind, "transfer_id": transfer_id,
            "memory_count": len(cards), "attachment_count": len(attachments), "attachment_bytes": manifest["attachment_bytes"], "manifest": manifest}


def _allowed_dynamic(name: str, version: int) -> bool:
    if name in _ROOT_FILES:
        return True
    if version >= 2 and (name == _ATTACH_INDEX or _BLOB_RE.fullmatch(name)):
        return True
    return False


def _read_package(path: str | os.PathLike[str]) -> tuple[dict[str, Any], dict[str, bytes]]:
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(str(p))
    # Read manifest first so we know which transfer version's file set is valid.
    if p.is_dir():
        mf = p / "manifest.json"
        if not mf.is_file():
            raise ValueError("not a valid Memory Box transfer package")
        manifest_raw = mf.read_bytes()
    else:
        if p.stat().st_size > MAX_PACKAGE_BYTES:
            raise ValueError("transfer package is too large")
        with zipfile.ZipFile(p, "r") as zf:
            try:
                info = zf.getinfo("manifest.json")
            except KeyError:
                raise ValueError("not a valid Memory Box transfer package")
            if info.file_size > MAX_ENTRY_BYTES:
                raise ValueError("manifest is too large")
            manifest_raw = zf.read(info)
    manifest = json.loads(manifest_raw.decode("utf-8"))
    version = int(manifest.get("format_version", 0))
    if manifest.get("format") != TRANSFER_FORMAT or version not in SUPPORTED_TRANSFER_VERSIONS:
        raise ValueError("unsupported Memory Box transfer format")

    files: dict[str, bytes] = {"manifest.json": manifest_raw}
    if p.is_dir():
        for name in _ROOT_FILES | ({_ATTACH_INDEX} if version >= 2 else set()):
            fp = p / name
            if fp.is_file():
                if fp.stat().st_size > MAX_ENTRY_BYTES:
                    raise ValueError(f"package entry too large: {name}")
                files[name] = fp.read_bytes()
        if version >= 2:
            blob_dir = p / "attachments" / "blobs"
            if blob_dir.is_dir():
                for fp in blob_dir.iterdir():
                    name = f"attachments/blobs/{fp.name}"
                    if fp.is_file() and _BLOB_RE.fullmatch(name):
                        if fp.stat().st_size > MAX_ENTRY_BYTES:
                            raise ValueError(f"package entry too large: {name}")
                        files[name] = fp.read_bytes()
    else:
        with zipfile.ZipFile(p, "r") as zf:
            infos = zf.infolist()
            total = sum(i.file_size for i in infos)
            if total > MAX_PACKAGE_BYTES:
                raise ValueError("uncompressed transfer package is too large")
            for info in infos:
                if not _allowed_dynamic(info.filename, version):
                    continue
                if info.file_size > MAX_ENTRY_BYTES:
                    raise ValueError(f"package entry too large: {info.filename}")
                files[info.filename] = zf.read(info)
    if sum(len(v) for v in files.values()) > MAX_PACKAGE_BYTES:
        raise ValueError("uncompressed transfer package is too large")
    if "memories.json" not in files:
        raise ValueError("not a valid Memory Box transfer package")
    for name, expected in (manifest.get("checksums") or {}).items():
        if name not in files:
            raise ValueError(f"package entry missing: {name}")
        if _sha256(files[name]) != str(expected).lower():
            raise ValueError(f"checksum mismatch: {name}")
    return manifest, files


def inspect_transfer_bundle(path: str | os.PathLike[str]) -> dict[str, Any]:
    manifest, files = _read_package(path)
    payload = json.loads(files["memories.json"].decode("utf-8"))
    cards = payload.get("memories") or []
    attachments = []
    if _ATTACH_INDEX in files:
        attachments = (json.loads(files[_ATTACH_INDEX].decode("utf-8")).get("attachments") or [])
    return {
        "ok": True,
        "manifest": manifest,
        "memory_count": len(cards),
        "attachment_count": len(attachments),
        "attachment_bytes": sum(int(a.get("size_bytes") or 0) for a in attachments),
        "titles": [{"memory_id": c.get("memory_id"), "title": c.get("title"), "category": c.get("category")} for c in cards[:100]],
        "attachments": [{"sha256": a.get("sha256"), "original_name": a.get("original_name"), "size_bytes": a.get("size_bytes"), "mime_type": a.get("mime_type")} for a in attachments[:100]],
    }


def _fingerprint(card: dict[str, Any]) -> str:
    core = {k: card.get(k) for k in ("title", "summary", "content", "category", "source_agent", "source_uri")}
    return _sha256(_json_bytes(core))


def import_transfer_bundle(path: str | os.PathLike[str], *, db_path=None, open_replay: bool = False) -> dict[str, Any]:
    local_device = _ensure_transfer_schema(db_path)
    manifest, files = _read_package(path)
    payload = json.loads(files["memories.json"].decode("utf-8"))
    cards = payload.get("memories") or []
    if not isinstance(cards, list) or len(cards) > MAX_MEMORIES:
        raise ValueError("invalid or oversized memory payload")
    attachment_items: list[dict[str, Any]] = []
    if _ATTACH_INDEX in files:
        attachment_items = json.loads(files[_ATTACH_INDEX].decode("utf-8")).get("attachments") or []
        if not isinstance(attachment_items, list) or len(attachment_items) > MAX_ATTACHMENTS:
            raise ValueError("invalid or oversized attachment payload")
    source_device = str(manifest.get("source_device_id") or "unknown")
    transfer_id = str(manifest.get("transfer_id") or "")
    result = {"ok": True, "transfer_id": transfer_id, "source_device_id": source_device,
              "local_device_id": local_device, "imported": 0, "skipped": 0, "remapped": 0,
              "attachments_imported": 0, "attachments_linked": 0, "attachment_bytes": 0,
              "mapping": {}, "replay_path": ""}

    init_db(db_path)
    for card in cards:
        origin_id = str(card.get("memory_id") or "").upper()
        if not re.fullmatch(r"M\d{6}", origin_id):
            origin_id = ""
        with _connect(db_path) as con:
            con.execute("BEGIN IMMEDIATE")
            mapped = None
            if origin_id:
                mapped = con.execute(
                    "SELECT local_memory_id FROM transfer_origins WHERE source_device_id=? AND origin_memory_id=?",
                    (source_device, origin_id),
                ).fetchone()
            if mapped:
                result["skipped"] += 1
                result["mapping"][origin_id] = mapped[0]
                continue
            existing = con.execute("SELECT * FROM memories WHERE memory_id=?", (origin_id,)).fetchone() if origin_id else None
            if existing and source_device == local_device:
                result["skipped"] += 1
                result["mapping"][origin_id] = origin_id
                con.execute("INSERT OR IGNORE INTO transfer_origins(source_device_id,origin_memory_id,local_memory_id,transfer_id,imported_at) VALUES(?,?,?,?,?)",
                            (source_device, origin_id, origin_id, transfer_id, utc_now()))
                continue
            if existing:
                existing_card = _row_to_dict(con, existing)
                if _fingerprint(existing_card) == _fingerprint(card):
                    local_id = origin_id
                    result["skipped"] += 1
                else:
                    local_id = _next_memory_id(con)
                    result["remapped"] += 1
            else:
                local_id = origin_id or _next_memory_id(con)
            if not existing or local_id != origin_id:
                now = utc_now()
                created = str(card.get("created_at") or now)
                updated = str(card.get("updated_at") or created)
                cur = con.execute(
                    "INSERT INTO memories(memory_id,title,summary,content,category,source_agent,source_type,source_uri,created_at,updated_at,pinned,favorite,archived) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (local_id, str(card.get("title") or "Imported memory"), str(card.get("summary") or ""), str(card.get("content") or ""),
                     str(card.get("category") or "general"), str(card.get("source_agent") or "import"), str(card.get("source_type") or "conversation"),
                     str(card.get("source_uri") or ""), created, updated, 1 if card.get("pinned") else 0, 1 if card.get("favorite") else 0, 1 if card.get("archived") else 0)
                )
                row_id = int(cur.lastrowid)
                _set_tags(con, row_id, [str(t) for t in (card.get("tags") or [])] + [f"import:{source_device[:8]}"])
                for i, v in enumerate(card.get("versions") or [], start=1):
                    snap = v.get("snapshot") if isinstance(v, dict) else v
                    con.execute(
                        "INSERT OR IGNORE INTO memory_versions(memory_id_fk,version_no,snapshot_json,created_at) VALUES(?,?,?,?)",
                        (row_id, i, json.dumps(snap, ensure_ascii=False), str((v or {}).get("created_at") if isinstance(v, dict) else "") or now),
                    )
                con.execute("INSERT INTO audit_log(action,memory_id,detail,created_at) VALUES('import',?,?,?)",
                            (local_id, f"{source_device}:{origin_id or '(no-id)'} via {transfer_id}", now))
                result["imported"] += 1
            if origin_id:
                con.execute("INSERT OR IGNORE INTO transfer_origins(source_device_id,origin_memory_id,local_memory_id,transfer_id,imported_at) VALUES(?,?,?,?,?)",
                            (source_device, origin_id, local_id, transfer_id, utc_now()))
                result["mapping"][origin_id] = local_id

    # Import verified attachment blobs and rebuild memory links using the origin->local mapping.
    for a in attachment_items:
        sha = str(a.get("sha256") or "").lower()
        package_path = str(a.get("package_path") or f"attachments/blobs/{sha}")
        if not re.fullmatch(r"[0-9a-f]{64}", sha) or package_path != f"attachments/blobs/{sha}":
            raise ValueError("invalid attachment descriptor")
        data = files.get(package_path)
        if data is None:
            raise ValueError(f"attachment blob missing: {sha}")
        if len(data) != int(a.get("size_bytes") or -1) or _sha256(data) != sha:
            raise ValueError(f"attachment integrity mismatch: {sha}")
        before_exists = (attachment_root(db_path) / sha[:2] / sha).exists()
        linked_local_ids: set[str] = set()
        for link in a.get("links") or []:
            origin_mid = str(link.get("memory_id") or "").upper()
            local_mid = result["mapping"].get(origin_mid)
            if not local_mid:
                continue
            add_attachment_bytes(local_mid, data, original_name=str(a.get("original_name") or "attachment.bin"),
                                 mime_type=str(a.get("mime_type") or "application/octet-stream"),
                                 role=str(link.get("role") or "attachment"), note=str(link.get("note") or ""),
                                 expected_sha256=sha, db_path=db_path)
            linked_local_ids.add(local_mid)
        if linked_local_ids:
            result["attachments_linked"] += len(linked_local_ids)
            result["attachment_bytes"] += len(data)
            if not before_exists:
                result["attachments_imported"] += 1

    # Build a destination-side replay receipt with restored local attachments.
    replay_dir = _runtime_home(db_path) / "imports" / (transfer_id or str(uuid.uuid4()))
    replay_dir.mkdir(parents=True, exist_ok=True)
    imported_ids = [result["mapping"].get(str(c.get("memory_id") or "").upper()) for c in cards]
    imported_ids = [x for x in imported_ids if x]
    local_cards = [_card_for_export(get_memory(mid, db_path), db_path) for mid in imported_ids]
    local_att = _attachment_catalog(local_cards, db_path)
    local_manifest = dict(manifest)
    local_viewer = _viewer_html(local_cards, local_manifest, local_att)
    replay = replay_dir / "viewer.html"
    replay.write_text(local_viewer, encoding="utf-8")
    (replay_dir / "resume.md").write_text(compose_context(imported_ids, db_path) if imported_ids else "# Memory Box Resume Context\n", encoding="utf-8")
    (replay_dir / "manifest.json").write_bytes(files["manifest.json"])
    # Mirror restored blobs into the replay folder so viewer.html links work offline.
    for a in local_att:
        src = attachment_root(db_path) / a["sha256"][:2] / a["sha256"]
        dest = replay_dir / a["package_path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.write_bytes(src.read_bytes())
    result["replay_path"] = str(replay.resolve())
    if open_replay:
        webbrowser.open(replay.resolve().as_uri())
    return result
