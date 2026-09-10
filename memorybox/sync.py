from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Iterable

from .crypto import decrypt_file_for_local_device, encrypt_file_for_recipients, fingerprint_public_key, inspect_encrypted_file, public_identity
from .db import _connect, init_db, utc_now
from .transfer import device_id, export_transfer_bundle, import_transfer_bundle, inspect_transfer_bundle

SYNC_FORMAT = "memorybox-folder-sync"
SYNC_VERSION = 2

PROVIDERS: dict[str, dict[str, str]] = {
    "baidu-netdisk": {"label": "百度网盘 / Baidu Netdisk", "kind": "cloud-folder"},
    "onedrive": {"label": "Microsoft OneDrive", "kind": "cloud-folder"},
    "nutstore": {"label": "坚果云 / Nutstore", "kind": "cloud-folder"},
    "syncthing": {"label": "Syncthing", "kind": "sync-folder"},
    "nas": {"label": "NAS / 网络共享", "kind": "network-folder"},
    "generic-folder": {"label": "其他同步文件夹", "kind": "sync-folder"},
}
ENCRYPTION_MODES = {"e2ee", "legacy-plaintext"}


def _ensure_schema(db_path=None) -> None:
    init_db(db_path)


def _norm_provider(provider: str) -> str:
    p = (provider or "generic-folder").strip().lower()
    aliases = {
        "baidu": "baidu-netdisk", "baidupan": "baidu-netdisk", "baidu-cloud": "baidu-netdisk",
        "百度": "baidu-netdisk", "百度云": "baidu-netdisk", "百度网盘": "baidu-netdisk",
        "one-drive": "onedrive", "坚果云": "nutstore", "folder": "generic-folder", "generic": "generic-folder",
    }
    p = aliases.get(p, p)
    if p not in PROVIDERS:
        raise ValueError(f"unsupported sync provider: {provider}")
    return p


def _norm_encryption_mode(mode: str | None) -> str:
    m = (mode or "e2ee").strip().lower()
    aliases = {"encrypted": "e2ee", "secure": "e2ee", "plaintext": "legacy-plaintext", "legacy": "legacy-plaintext"}
    m = aliases.get(m, m)
    if m not in ENCRYPTION_MODES:
        raise ValueError(f"unsupported encryption mode: {mode}")
    return m


def _endpoint_sync_root(root_path: str | os.PathLike[str]) -> Path:
    return Path(root_path).expanduser().resolve() / "MemoryBoxSync"


def configure_sync_folder(root_path: str | os.PathLike[str], *, provider: str = "generic-folder",
                          name: str | None = None, auto_import: bool = True,
                          encryption_mode: str = "e2ee", endpoint_id: str | None = None, db_path=None) -> dict[str, Any]:
    _ensure_schema(db_path)
    provider = _norm_provider(provider)
    encryption_mode = _norm_encryption_mode(encryption_mode)
    root = Path(root_path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    sync_root = _endpoint_sync_root(root)
    (sync_root / "packages").mkdir(parents=True, exist_ok=True)
    (sync_root / "devices").mkdir(parents=True, exist_ok=True)
    marker = {"format": SYNC_FORMAT, "version": SYNC_VERSION, "provider": provider, "created_or_seen_at": utc_now()}
    marker_path = sync_root / "memorybox-sync.json"
    if not marker_path.exists():
        marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    eid = endpoint_id or f"sync-{uuid.uuid4().hex[:12]}"
    now = utc_now(); label = name or PROVIDERS[provider]["label"]
    with _connect(db_path) as con:
        con.execute("""
        INSERT INTO sync_endpoints(endpoint_id,name,provider,root_path,enabled,auto_import,encryption_mode,created_at,updated_at)
        VALUES(?,?,?,?,1,?,?,?,?)
        ON CONFLICT(endpoint_id) DO UPDATE SET name=excluded.name,provider=excluded.provider,
          root_path=excluded.root_path,enabled=1,auto_import=excluded.auto_import,
          encryption_mode=excluded.encryption_mode,updated_at=excluded.updated_at
        """, (eid, label, provider, str(root), 1 if auto_import else 0, encryption_mode, now, now))
    _write_device_presence(eid, root, db_path=db_path)
    return get_sync_endpoint(eid, db_path=db_path)


def get_sync_endpoint(endpoint_id: str, db_path=None) -> dict[str, Any]:
    _ensure_schema(db_path)
    with _connect(db_path) as con:
        r = con.execute("SELECT * FROM sync_endpoints WHERE endpoint_id=?", (endpoint_id,)).fetchone()
        if not r: raise KeyError(endpoint_id)
        d = dict(r)
    d["enabled"] = bool(d["enabled"]); d["auto_import"] = bool(d["auto_import"])
    d["provider_label"] = PROVIDERS.get(d["provider"], {}).get("label", d["provider"])
    d["sync_root"] = str(_endpoint_sync_root(d["root_path"])); d["available"] = Path(d["root_path"]).exists()
    d["e2ee"] = d.get("encryption_mode") == "e2ee"
    return d


def list_sync_endpoints(db_path=None) -> list[dict[str, Any]]:
    _ensure_schema(db_path)
    with _connect(db_path) as con:
        ids = [r[0] for r in con.execute("SELECT endpoint_id FROM sync_endpoints ORDER BY created_at").fetchall()]
    return [get_sync_endpoint(x, db_path=db_path) for x in ids]


def set_sync_encryption(endpoint_id: str, mode: str, db_path=None) -> dict[str, Any]:
    mode = _norm_encryption_mode(mode); _ensure_schema(db_path)
    with _connect(db_path) as con:
        cur = con.execute("UPDATE sync_endpoints SET encryption_mode=?,updated_at=? WHERE endpoint_id=?", (mode, utc_now(), endpoint_id))
        if cur.rowcount == 0: raise KeyError(endpoint_id)
    ep = get_sync_endpoint(endpoint_id, db_path=db_path)
    _write_device_presence(endpoint_id, Path(ep["root_path"]), db_path=db_path)
    return ep


def remove_sync_endpoint(endpoint_id: str, db_path=None) -> dict[str, Any]:
    _ensure_schema(db_path)
    with _connect(db_path) as con:
        r = con.execute("SELECT 1 FROM sync_endpoints WHERE endpoint_id=?", (endpoint_id,)).fetchone()
        if not r: raise KeyError(endpoint_id)
        con.execute("DELETE FROM trusted_devices WHERE endpoint_id=?", (endpoint_id,))
        con.execute("DELETE FROM sync_endpoints WHERE endpoint_id=?", (endpoint_id,))
    return {"ok": True, "endpoint_id": endpoint_id, "cloud_files_deleted": False}


def set_sync_endpoint_enabled(endpoint_id: str, enabled: bool, db_path=None) -> dict[str, Any]:
    _ensure_schema(db_path)
    with _connect(db_path) as con:
        cur = con.execute("UPDATE sync_endpoints SET enabled=?,updated_at=? WHERE endpoint_id=?", (1 if enabled else 0, utc_now(), endpoint_id))
        if cur.rowcount == 0: raise KeyError(endpoint_id)
    return get_sync_endpoint(endpoint_id, db_path=db_path)


def _write_device_presence(endpoint_id: str, root: Path, db_path=None) -> None:
    did = device_id(db_path); ident = public_identity(db_path)
    sync_root = _endpoint_sync_root(root); (sync_root / "devices").mkdir(parents=True, exist_ok=True)
    info = {
        "device_id": did,
        "device_name": os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "MemoryBox device",
        "last_seen_at": utc_now(), "endpoint_id": endpoint_id,
        "e2ee_supported": True, "e2ee_public_key": ident["public_key"], "e2ee_fingerprint": ident["fingerprint"],
    }
    tmp = sync_root / "devices" / f"{did}.json.tmp"; final = sync_root / "devices" / f"{did}.json"
    tmp.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); tmp.replace(final)


def _presence_map(endpoint_id: str, db_path=None) -> dict[str, dict[str, Any]]:
    ep = get_sync_endpoint(endpoint_id, db_path=db_path); root = Path(ep["sync_root"]) / "devices"; out = {}
    if root.exists():
        for p in root.glob("*.json"):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(d, dict) and d.get("device_id"): out[str(d["device_id"])] = d
            except Exception: pass
    return out


def list_trusted_devices(endpoint_id: str, db_path=None) -> list[dict[str, Any]]:
    _ensure_schema(db_path)
    with _connect(db_path) as con:
        rows = con.execute("SELECT * FROM trusted_devices WHERE endpoint_id=? AND revoked_at='' ORDER BY trusted_at", (endpoint_id,)).fetchall()
        return [dict(r) for r in rows]


def list_sync_devices(endpoint_id: str, db_path=None) -> list[dict[str, Any]]:
    ep = get_sync_endpoint(endpoint_id, db_path=db_path); _write_device_presence(endpoint_id, Path(ep["root_path"]), db_path=db_path)
    trusted = {x["device_id"]: x for x in list_trusted_devices(endpoint_id, db_path=db_path)}
    out = []
    for d in _presence_map(endpoint_id, db_path=db_path).values():
        d = dict(d); d["is_local"] = d.get("device_id") == device_id(db_path); d["trusted"] = d.get("device_id") in trusted
        if d.get("e2ee_public_key"):
            try: d["e2ee_fingerprint"] = fingerprint_public_key(d["e2ee_public_key"])
            except Exception: d["e2ee_valid"] = False
        out.append(d)
    return sorted(out, key=lambda x: str(x.get("last_seen_at") or ""), reverse=True)


def trust_sync_device(endpoint_id: str, remote_device_id: str, *, expected_fingerprint: str | None = None, db_path=None) -> dict[str, Any]:
    ep = get_sync_endpoint(endpoint_id, db_path=db_path); _write_device_presence(endpoint_id, Path(ep["root_path"]), db_path=db_path)
    if remote_device_id == device_id(db_path): raise ValueError("local device does not need to be trusted")
    d = _presence_map(endpoint_id, db_path=db_path).get(remote_device_id)
    if not d: raise KeyError(f"device not visible in sync folder: {remote_device_id}")
    pub = str(d.get("e2ee_public_key") or ""); fp = str(d.get("e2ee_fingerprint") or "")
    if not pub: raise ValueError("remote device does not advertise an E2EE public key")
    actual = fingerprint_public_key(pub)
    if fp and fp != actual: raise ValueError("remote device public-key fingerprint mismatch")
    if expected_fingerprint and expected_fingerprint.strip().upper() != actual.upper(): raise ValueError("fingerprint confirmation failed")
    with _connect(db_path) as con:
        con.execute("""INSERT INTO trusted_devices(endpoint_id,device_id,device_name,public_key,fingerprint,trusted_at,revoked_at)
        VALUES(?,?,?,?,?,?,'') ON CONFLICT(endpoint_id,device_id) DO UPDATE SET device_name=excluded.device_name,
        public_key=excluded.public_key,fingerprint=excluded.fingerprint,trusted_at=excluded.trusted_at,revoked_at=''""",
        (endpoint_id, remote_device_id, str(d.get("device_name") or ""), pub, actual, utc_now()))
    return {"ok": True, "endpoint_id": endpoint_id, "device_id": remote_device_id, "device_name": d.get("device_name", ""), "fingerprint": actual, "trusted": True}


def revoke_sync_device(endpoint_id: str, remote_device_id: str, db_path=None) -> dict[str, Any]:
    _ensure_schema(db_path)
    with _connect(db_path) as con:
        cur = con.execute("UPDATE trusted_devices SET revoked_at=? WHERE endpoint_id=? AND device_id=? AND revoked_at=''", (utc_now(), endpoint_id, remote_device_id))
    return {"ok": True, "endpoint_id": endpoint_id, "device_id": remote_device_id, "revoked": bool(cur.rowcount)}


def sync_security_status(endpoint_id: str, db_path=None) -> dict[str, Any]:
    ep = get_sync_endpoint(endpoint_id, db_path=db_path); local = public_identity(db_path)
    return {"endpoint_id": endpoint_id, "encryption_mode": ep["encryption_mode"], "e2ee": ep["e2ee"],
            "local_device": local, "trusted_devices": list_trusted_devices(endpoint_id, db_path=db_path)}


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()


def _recipient_identities(endpoint_id: str, db_path=None) -> list[dict[str, str]]:
    recipients = [{**public_identity(db_path), "device_name": "local"}]
    recipients.extend({"device_id": x["device_id"], "public_key": x["public_key"], "fingerprint": x["fingerprint"], "device_name": x.get("device_name", "")} for x in list_trusted_devices(endpoint_id, db_path=db_path))
    return recipients


def publish_to_sync(endpoint_id: str, *, memory_ids: Iterable[str] | None = None,
                    query: str | None = None, category: str | None = None,
                    include_archived: bool = False, db_path=None) -> dict[str, Any]:
    ep = get_sync_endpoint(endpoint_id, db_path=db_path)
    if not ep["enabled"]: raise ValueError("sync endpoint is disabled")
    root = Path(ep["root_path"])
    if not root.exists(): raise FileNotFoundError(f"sync folder is unavailable: {root}")
    _write_device_presence(endpoint_id, root, db_path=db_path)
    did = device_id(db_path); dest_dir = Path(ep["sync_root"]) / "packages" / did; dest_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memorybox-sync-") as td:
        temp_pack = Path(td) / "out.mboxpack"
        result = export_transfer_bundle(temp_pack, memory_ids=memory_ids, query=query, category=category, include_archived=include_archived, db_path=db_path)
        if ep["encryption_mode"] == "e2ee":
            recipients = _recipient_identities(endpoint_id, db_path=db_path)
            final = dest_dir / f"{result['transfer_id']}.mboxenc"; tmp = final.with_suffix(".mboxenc.uploading")
            enc = encrypt_file_for_recipients(temp_pack, tmp, recipients=recipients, transfer_id=result["transfer_id"], source_device_id=did, db_path=db_path)
            tmp.replace(final)
            encrypted = True
        else:
            final = dest_dir / f"{result['transfer_id']}.mboxpack"; tmp = final.with_suffix(".mboxpack.uploading")
            shutil.copy2(temp_pack, tmp); tmp.replace(final); enc = {}; encrypted = False
    return {"ok": True, "endpoint_id": endpoint_id, "provider": ep["provider"], "path": str(final),
            "transfer_id": result["transfer_id"], "memory_count": result["memory_count"], "attachment_count": result.get("attachment_count", 0),
            "sha256": _file_sha256(final), "encrypted": encrypted, "encryption_mode": ep["encryption_mode"],
            "recipient_device_ids": enc.get("recipient_device_ids", [])}


def _receipt_exists(endpoint_id: str, transfer_id: str, source_device_id: str, db_path=None) -> bool:
    with _connect(db_path) as con:
        return con.execute("SELECT 1 FROM sync_receipts WHERE endpoint_id=? AND transfer_id=? AND source_device_id=?", (endpoint_id, transfer_id, source_device_id)).fetchone() is not None


def _record_receipt(endpoint_id: str, transfer_id: str, source_device_id: str, package_sha256: str, status: str, detail: str = "", db_path=None) -> None:
    with _connect(db_path) as con:
        con.execute("""INSERT OR REPLACE INTO sync_receipts(endpoint_id,transfer_id,source_device_id,package_sha256,status,detail,processed_at)
        VALUES(?,?,?,?,?,?,?)""", (endpoint_id, transfer_id, source_device_id, package_sha256, status, detail[:4000], utc_now()))


def receive_from_sync(endpoint_id: str, *, limit: int = 200, db_path=None) -> dict[str, Any]:
    ep = get_sync_endpoint(endpoint_id, db_path=db_path)
    if not ep["enabled"]: return {"ok": True, "endpoint_id": endpoint_id, "imported_packages": 0, "skipped_packages": 0, "errors": []}
    root = Path(ep["root_path"])
    if not root.exists(): raise FileNotFoundError(f"sync folder is unavailable: {root}")
    _write_device_presence(endpoint_id, root, db_path=db_path)
    packages_root = Path(ep["sync_root"]) / "packages"; local = device_id(db_path)
    out = {"ok": True, "endpoint_id": endpoint_id, "provider": ep["provider"], "encryption_mode": ep["encryption_mode"], "imported_packages": 0,
           "skipped_packages": 0, "memories_imported": 0, "attachments_imported": 0, "encrypted_imports": 0, "errors": []}
    if not packages_root.exists(): return out
    candidates = sorted([*packages_root.glob("*/*.mboxenc"), *packages_root.glob("*/*.mboxpack")], key=lambda p: p.stat().st_mtime)[:max(1, limit)]
    for pack in candidates:
        try:
            is_enc = pack.suffix.lower() == ".mboxenc"
            if ep["encryption_mode"] == "e2ee" and not is_enc:
                out["skipped_packages"] += 1; continue
            if is_enc:
                h = inspect_encrypted_file(pack)["header"]; source = str(h.get("source_device_id") or "unknown"); tid = str(h.get("transfer_id") or "")
            else:
                man = inspect_transfer_bundle(pack)["manifest"]; source = str(man.get("source_device_id") or "unknown"); tid = str(man.get("transfer_id") or "")
            if source == local: out["skipped_packages"] += 1; continue
            if not tid: raise ValueError("sync package has no transfer_id")
            if _receipt_exists(endpoint_id, tid, source, db_path=db_path): out["skipped_packages"] += 1; continue
            digest = _file_sha256(pack)
            with tempfile.TemporaryDirectory(prefix="memorybox-sync-import-") as td:
                import_path = pack
                if is_enc:
                    # Cloud E2EE is mutually authenticated: the recipient must also trust the sender.
                    trusted_sender = next((x for x in list_trusted_devices(endpoint_id, db_path=db_path) if x["device_id"] == source), None)
                    if not trusted_sender:
                        out["skipped_packages"] += 1; continue
                    dec = Path(td) / "decrypted.mboxpack"
                    try: decrypt_file_for_local_device(pack, dec, expected_sender_public_key=trusted_sender["public_key"], db_path=db_path)
                    except PermissionError:
                        out["skipped_packages"] += 1; continue
                    import_path = dec
                result = import_transfer_bundle(import_path, db_path=db_path)
            _record_receipt(endpoint_id, tid, source, digest, "imported", json.dumps({"mapping": result.get("mapping", {}), "encrypted": is_enc}, ensure_ascii=False), db_path=db_path)
            out["imported_packages"] += 1; out["memories_imported"] += int(result.get("imported", 0)); out["attachments_imported"] += int(result.get("attachments_imported", 0)); out["encrypted_imports"] += int(is_enc)
        except Exception as exc:
            out["errors"].append({"path": str(pack), "error": str(exc)})
    return out


def sync_now(endpoint_id: str, *, publish: bool = False, memory_ids: Iterable[str] | None = None,
             query: str | None = None, category: str | None = None, db_path=None) -> dict[str, Any]:
    sent = publish_to_sync(endpoint_id, memory_ids=memory_ids, query=query, category=category, db_path=db_path) if publish else None
    return {"ok": True, "sent": sent, "received": receive_from_sync(endpoint_id, db_path=db_path)}


def sync_all(*, receive_only: bool = True, db_path=None) -> list[dict[str, Any]]:
    results = []
    for ep in list_sync_endpoints(db_path=db_path):
        if not ep["enabled"]: continue
        try: results.append({"endpoint_id": ep["endpoint_id"], **sync_now(ep["endpoint_id"], publish=not receive_only, db_path=db_path)})
        except Exception as exc: results.append({"endpoint_id": ep["endpoint_id"], "ok": False, "error": str(exc)})
    return results


def detect_sync_folders() -> list[dict[str, Any]]:
    h = Path.home(); candidates: list[tuple[str, Path, str]] = []
    for env_name in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        value = os.environ.get(env_name)
        if value: candidates.append(("onedrive", Path(value), f"env:{env_name}"))
    for name in ("BaiduNetdisk", "BaiduNetdiskSync", "BaiduSyncdisk", "百度网盘", "百度网盘同步空间"):
        candidates.append(("baidu-netdisk", h / name, "common-folder-name"))
    for name in ("Nutstore Files", "Nutstore", "坚果云"): candidates.append(("nutstore", h / name, "common-folder-name"))
    for name in ("Syncthing", "Sync"): candidates.append(("syncthing", h / name, "common-folder-name"))
    seen = set(); out = []
    for provider, p, reason in candidates:
        try: rp = p.expanduser().resolve()
        except Exception: continue
        key = (provider, str(rp).lower())
        if key in seen or not rp.exists() or not rp.is_dir(): continue
        seen.add(key); out.append({"provider": provider, "provider_label": PROVIDERS[provider]["label"], "path": str(rp), "reason": reason})
    return out


class SyncMonitor:
    def __init__(self, interval_seconds: float = 15.0, db_path=None):
        self.interval_seconds = max(5.0, float(interval_seconds)); self.db_path = db_path; self._stop = threading.Event(); self._thread: threading.Thread | None = None
    def start(self) -> "SyncMonitor":
        if self._thread and self._thread.is_alive(): return self
        self._thread = threading.Thread(target=self._run, name="MemoryBoxSyncMonitor", daemon=True); self._thread.start(); return self
    def stop(self) -> None: self._stop.set()
    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                for ep in list_sync_endpoints(db_path=self.db_path):
                    if ep["enabled"] and ep["auto_import"]:
                        try: receive_from_sync(ep["endpoint_id"], db_path=self.db_path)
                        except Exception: pass
            except Exception: pass
            self._stop.wait(self.interval_seconds)
