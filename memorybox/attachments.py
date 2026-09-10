from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
from pathlib import Path
from typing import Any

from .db import _connect, default_home, init_db, utc_now

DEFAULT_MAX_ATTACHMENT_BYTES = 1024 * 1024 * 1024  # 1 GiB


def max_attachment_bytes() -> int:
    raw = os.environ.get("MEMORYBOX_MAX_ATTACHMENT_BYTES")
    if not raw:
        return DEFAULT_MAX_ATTACHMENT_BYTES
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_MAX_ATTACHMENT_BYTES


def attachment_root(db_path: str | os.PathLike[str] | None = None) -> Path:
    if db_path is None:
        root = default_home() / "attachments"
    else:
        root = Path(db_path).expanduser().resolve().parent / "attachments"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_name(name: str) -> str:
    name = Path(str(name or "attachment.bin")).name.strip() or "attachment.bin"
    return name.replace("\x00", "")[:240]


def _sha256_file(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
            size += len(chunk)
            if size > max_attachment_bytes():
                raise ValueError("attachment exceeds configured size limit")
    return h.hexdigest(), size


def _blob_relpath(sha256: str) -> str:
    return f"{sha256[:2]}/{sha256}"


def blob_path(sha256: str, db_path: str | os.PathLike[str] | None = None) -> Path:
    if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256.lower()):
        raise ValueError("invalid attachment hash")
    return attachment_root(db_path) / _blob_relpath(sha256.lower())


def _register_attachment(memory_id: str, *, sha256: str, size_bytes: int, original_name: str,
                         mime_type: str, role: str, note: str, db_path=None) -> dict[str, Any]:
    init_db(db_path)
    with _connect(db_path) as con:
        con.execute("BEGIN IMMEDIATE")
        m = con.execute("SELECT id FROM memories WHERE memory_id=?", (memory_id.upper(),)).fetchone()
        if not m:
            raise KeyError(memory_id)
        rel = _blob_relpath(sha256)
        con.execute(
            "INSERT OR IGNORE INTO attachments(sha256,original_name,mime_type,size_bytes,stored_relpath,created_at) VALUES(?,?,?,?,?,?)",
            (sha256, _safe_name(original_name), mime_type or "application/octet-stream", int(size_bytes), rel, utc_now()),
        )
        a = con.execute("SELECT * FROM attachments WHERE sha256=?", (sha256,)).fetchone()
        con.execute(
            "INSERT INTO memory_attachments(memory_id_fk,attachment_id,role,note,created_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(memory_id_fk,attachment_id) DO UPDATE SET role=excluded.role,note=excluded.note",
            (m["id"], a["id"], role or "attachment", note or "", utc_now()),
        )
        con.execute("INSERT INTO audit_log(action,memory_id,detail,created_at) VALUES('attach',?,?,?)",
                    (memory_id.upper(), sha256, utc_now()))
    return get_attachment(sha256, memory_id=memory_id, db_path=db_path)


def add_attachment(memory_id: str, file_path: str | os.PathLike[str], *, role: str = "attachment",
                   note: str = "", db_path=None) -> dict[str, Any]:
    src = Path(file_path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(str(src))
    sha256, size = _sha256_file(src)
    dest = blob_path(sha256, db_path)
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + f".tmp-{os.getpid()}")
        shutil.copyfile(src, tmp)
        copied_sha, copied_size = _sha256_file(tmp)
        if copied_sha != sha256 or copied_size != size:
            tmp.unlink(missing_ok=True)
            raise IOError("attachment copy verification failed")
        try:
            os.replace(tmp, dest)
        except FileExistsError:
            tmp.unlink(missing_ok=True)
    mime = mimetypes.guess_type(src.name)[0] or "application/octet-stream"
    return _register_attachment(memory_id, sha256=sha256, size_bytes=size, original_name=src.name,
                                mime_type=mime, role=role, note=note, db_path=db_path)


def add_attachment_bytes(memory_id: str, data: bytes, *, original_name: str, mime_type: str | None = None,
                         role: str = "attachment", note: str = "", expected_sha256: str | None = None,
                         db_path=None) -> dict[str, Any]:
    if len(data) > max_attachment_bytes():
        raise ValueError("attachment exceeds configured size limit")
    sha256 = hashlib.sha256(data).hexdigest()
    if expected_sha256 and sha256 != expected_sha256.lower():
        raise ValueError("attachment checksum mismatch")
    dest = blob_path(sha256, db_path)
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + f".tmp-{os.getpid()}")
        tmp.write_bytes(data)
        if hashlib.sha256(tmp.read_bytes()).hexdigest() != sha256:
            tmp.unlink(missing_ok=True)
            raise IOError("attachment write verification failed")
        try:
            os.replace(tmp, dest)
        except FileExistsError:
            tmp.unlink(missing_ok=True)
    mime = mime_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    return _register_attachment(memory_id, sha256=sha256, size_bytes=len(data), original_name=original_name,
                                mime_type=mime, role=role, note=note, db_path=db_path)


def list_attachments(memory_id: str, db_path=None) -> list[dict[str, Any]]:
    init_db(db_path)
    with _connect(db_path) as con:
        rows = con.execute(
            "SELECT a.*,ma.role,ma.note,ma.created_at AS linked_at FROM attachments a "
            "JOIN memory_attachments ma ON ma.attachment_id=a.id "
            "JOIN memories m ON m.id=ma.memory_id_fk WHERE m.memory_id=? ORDER BY ma.created_at,a.id",
            (memory_id.upper(),),
        ).fetchall()
        return [
            {**dict(r), "local_path": str((attachment_root(db_path) / r["stored_relpath"]).resolve())}
            for r in rows
        ]


def get_attachment(sha256: str, *, memory_id: str | None = None, db_path=None) -> dict[str, Any]:
    init_db(db_path)
    with _connect(db_path) as con:
        if memory_id:
            row = con.execute(
                "SELECT a.*,ma.role,ma.note,ma.created_at AS linked_at FROM attachments a "
                "JOIN memory_attachments ma ON ma.attachment_id=a.id JOIN memories m ON m.id=ma.memory_id_fk "
                "WHERE a.sha256=? AND m.memory_id=?",
                (sha256.lower(), memory_id.upper()),
            ).fetchone()
        else:
            row = con.execute("SELECT a.*,'' AS role,'' AS note,a.created_at AS linked_at FROM attachments a WHERE a.sha256=?",
                              (sha256.lower(),)).fetchone()
        if not row:
            raise KeyError(sha256)
        d = dict(row)
        d["local_path"] = str((attachment_root(db_path) / d["stored_relpath"]).resolve())
        return d


def remove_attachment(memory_id: str, sha256: str, *, delete_orphan_blob: bool = False, db_path=None) -> dict[str, Any]:
    init_db(db_path)
    with _connect(db_path) as con:
        con.execute("BEGIN IMMEDIATE")
        m = con.execute("SELECT id FROM memories WHERE memory_id=?", (memory_id.upper(),)).fetchone()
        a = con.execute("SELECT id,stored_relpath FROM attachments WHERE sha256=?", (sha256.lower(),)).fetchone()
        if not m or not a:
            raise KeyError(memory_id if not m else sha256)
        con.execute("DELETE FROM memory_attachments WHERE memory_id_fk=? AND attachment_id=?", (m["id"], a["id"]))
        refs = con.execute("SELECT COUNT(*) FROM memory_attachments WHERE attachment_id=?", (a["id"],)).fetchone()[0]
        removed_blob = False
        if delete_orphan_blob and refs == 0:
            con.execute("DELETE FROM attachments WHERE id=?", (a["id"],))
            fp = attachment_root(db_path) / a["stored_relpath"]
            fp.unlink(missing_ok=True)
            removed_blob = True
        con.execute("INSERT INTO audit_log(action,memory_id,detail,created_at) VALUES('detach',?,?,?)",
                    (memory_id.upper(), sha256.lower(), utc_now()))
    return {"ok": True, "memory_id": memory_id.upper(), "sha256": sha256.lower(), "blob_deleted": removed_blob}
