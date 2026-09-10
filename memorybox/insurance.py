from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .attachments import attachment_root
from .crypto import decrypt_file_for_local_device, encrypt_file_for_recipients, inspect_encrypted_file, public_identity
from .db import _connect, default_db_path, default_home, init_db, utc_now
from .recovery import RECOVERY_EXT, inspect_recovery_kit
from .sync import get_sync_endpoint, list_sync_endpoints
from .transfer import device_id, export_transfer_bundle, inspect_transfer_bundle

INSURANCE_FORMAT = "memorybox-insurance"
INSURANCE_VERSION = 1
DEFAULT_INTERVAL_HOURS = 24
DEFAULT_RETENTION = 7
DEFAULT_MAX_AGE_HOURS = 36


def _parse_utc(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _age_hours(text: str | None) -> float | None:
    dt = _parse_utc(text)
    if not dt:
        return None
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()



def _sqlite_snapshot(output: Path, db_path=None) -> dict[str, Any]:
    """Create a consistent SQLite snapshot using SQLite's online backup API."""
    init_db(db_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists(): output.unlink()
    src = _connect(db_path)
    dst = sqlite3.connect(str(output))
    try:
        src.backup(dst)
        row = dst.execute("PRAGMA quick_check").fetchone()
        if not row or str(row[0]) != "ok":
            raise ValueError("SQLite snapshot failed quick_check")
    finally:
        dst.close(); src.close()
    return {"path": str(output), "sha256": _sha256_file(output), "size_bytes": output.stat().st_size}


def _attachment_index_bytes(db_path=None) -> bytes:
    init_db(db_path)
    with _connect(db_path) as con:
        rows = [dict(r) for r in con.execute("SELECT sha256,original_name,mime_type,size_bytes,stored_relpath,created_at FROM attachments ORDER BY id").fetchall()]
    payload = {"format": "memorybox-attachment-index", "version": 1, "created_at": utc_now(), "attachments": rows}
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _create_plain_insurance_archive(output: Path, db_path=None) -> dict[str, Any]:
    """Build the plaintext insurance archive in a temporary local location only."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memorybox-insurance-payload-") as td:
        td = Path(td)
        pack = td / "full.mboxpack"
        exported = export_transfer_bundle(pack, include_archived=True, db_path=db_path)
        dbsnap = td / "memorybox.db"
        dbmeta = _sqlite_snapshot(dbsnap, db_path=db_path)
        att_index = _attachment_index_bytes(db_path)
        files = {
            "memorybox.db": dbsnap.read_bytes(),
            "full.mboxpack": pack.read_bytes(),
            "attachments-index.json": att_index,
        }
        manifest = {
            "format": INSURANCE_FORMAT,
            "version": INSURANCE_VERSION,
            "created_at": utc_now(),
            "source_device_id": device_id(db_path),
            "transfer_id": exported["transfer_id"],
            "memory_count": exported["memory_count"],
            "attachment_count": exported.get("attachment_count", 0),
            "attachment_bytes": exported.get("attachment_bytes", 0),
            "database_size_bytes": dbmeta["size_bytes"],
            "checksums": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
        }
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zf:
            zf.writestr("manifest.json", manifest_bytes)
            for name, data in files.items(): zf.writestr(name, data)
    return {"path": str(output), "manifest": manifest, "transfer": exported}


def _inspect_plain_insurance_archive(path: Path, *, deep_database: bool = True) -> dict[str, Any]:
    allowed = {"manifest.json", "memorybox.db", "full.mboxpack", "attachments-index.json"}
    with zipfile.ZipFile(path, "r") as zf:
        names = set(zf.namelist())
        if not {"manifest.json", "memorybox.db", "full.mboxpack"} <= names:
            raise ValueError("not a valid Memory Box insurance snapshot")
        # Unknown entries are ignored, never extracted. Known entries are read by exact name only.
        manifest_raw = zf.read("manifest.json")
        manifest = json.loads(manifest_raw.decode("utf-8"))
        if manifest.get("format") != INSURANCE_FORMAT or int(manifest.get("version", 0)) != INSURANCE_VERSION:
            raise ValueError("unsupported Memory Box insurance snapshot")
        known = {name: zf.read(name) for name in names & allowed if name != "manifest.json"}
    for name, expected in (manifest.get("checksums") or {}).items():
        if name not in known: raise ValueError(f"insurance entry missing: {name}")
        if hashlib.sha256(known[name]).hexdigest() != str(expected).lower(): raise ValueError(f"insurance checksum mismatch: {name}")
    with tempfile.TemporaryDirectory(prefix="memorybox-insurance-inspect-") as td:
        td=Path(td)
        pack=td/"full.mboxpack"; pack.write_bytes(known["full.mboxpack"])
        info=inspect_transfer_bundle(pack)
        db_ok=True; db_result="not_checked"
        if deep_database:
            dbf=td/"memorybox.db"; dbf.write_bytes(known["memorybox.db"])
            con=sqlite3.connect(str(dbf))
            try: db_result=str(con.execute("PRAGMA quick_check").fetchone()[0]); db_ok=(db_result=="ok")
            finally: con.close()
        if not db_ok: raise ValueError("insurance SQLite snapshot failed integrity check")
    return {"ok": True, "manifest": manifest, "memory_count": info["memory_count"], "attachment_count": info["attachment_count"],
            "attachment_bytes": info["attachment_bytes"], "database_check": db_result, "database_snapshot_included": True,
            "attachment_index_included": "attachments-index.json" in known}



def list_insurance_snapshots(endpoint_id: str, db_path=None) -> list[dict[str, Any]]:
    ep=get_sync_endpoint(endpoint_id,db_path=db_path)
    root=_insurance_dir(ep,db_path=db_path)
    out=[]
    for p in sorted((x for x in root.glob("*.mboxenc") if x.is_file()),key=lambda x:x.stat().st_mtime,reverse=True):
        try:
            h=inspect_encrypted_file(p)["header"]
            out.append({"path":str(p),"size_bytes":p.stat().st_size,"modified_at":datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat().replace('+00:00','Z'),"transfer_id":h.get("transfer_id"),"source_device_id":h.get("source_device_id"),"sha256":_sha256_file(p)})
        except Exception as exc:
            out.append({"path":str(p),"size_bytes":p.stat().st_size,"error":str(exc)})
    return out


def restore_latest_insurance(endpoint_id: str, *, db_path=None) -> dict[str, Any]:
    snaps=list_insurance_snapshots(endpoint_id,db_path=db_path)
    good=[x for x in snaps if not x.get("error")]
    if not good: raise FileNotFoundError("no insurance snapshot addressed to this recovered device was found")
    return restore_insurance_snapshot(good[0]["path"],db_path=db_path)


def restore_insurance_snapshot(encrypted_path: str | os.PathLike[str], *, db_path=None) -> dict[str, Any]:
    """Decrypt and import the portable logical payload from an insurance snapshot. Raw SQLite is retained only as backup evidence."""
    from .transfer import import_transfer_bundle
    src=Path(encrypted_path).expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="memorybox-insurance-restore-") as td:
        td=Path(td); plain=td/"insurance.mbxinsurance"
        decrypt_file_for_local_device(src, plain, db_path=db_path)
        _inspect_plain_insurance_archive(plain, deep_database=True)
        with zipfile.ZipFile(plain,"r") as zf: pack_bytes=zf.read("full.mboxpack")
        pack=td/"full.mboxpack"; pack.write_bytes(pack_bytes)
        imported=import_transfer_bundle(pack,db_path=db_path)
    return {"ok": True, "encrypted_path": str(src), "import": imported}


def configure_insurance(endpoint_id: str, *, enabled: bool = True, interval_hours: int = DEFAULT_INTERVAL_HOURS,
                        retention: int = DEFAULT_RETENTION, deep_verify: bool = False, db_path=None) -> dict[str, Any]:
    init_db(db_path)
    ep = get_sync_endpoint(endpoint_id, db_path=db_path)
    if ep.get("encryption_mode") != "e2ee":
        raise ValueError("automatic insurance requires an E2EE sync endpoint")
    interval_hours = max(1, min(int(interval_hours), 24 * 30))
    retention = max(2, min(int(retention), 90))
    now = utc_now()
    with _connect(db_path) as con:
        con.execute(
            """INSERT INTO insurance_settings(profile_id,enabled,endpoint_id,interval_hours,retention,deep_verify,created_at,updated_at)
               VALUES('default',?,?,?,?,?,?,?)
               ON CONFLICT(profile_id) DO UPDATE SET enabled=excluded.enabled,endpoint_id=excluded.endpoint_id,
                 interval_hours=excluded.interval_hours,retention=excluded.retention,deep_verify=excluded.deep_verify,updated_at=excluded.updated_at""",
            (1 if enabled else 0, endpoint_id, interval_hours, retention, 1 if deep_verify else 0, now, now),
        )
    return insurance_settings(db_path)


def disable_insurance(db_path=None) -> dict[str, Any]:
    init_db(db_path)
    with _connect(db_path) as con:
        con.execute("UPDATE insurance_settings SET enabled=0,updated_at=? WHERE profile_id='default'", (utc_now(),))
    return insurance_settings(db_path)


def insurance_settings(db_path=None) -> dict[str, Any]:
    init_db(db_path)
    with _connect(db_path) as con:
        row = con.execute("SELECT * FROM insurance_settings WHERE profile_id='default'").fetchone()
        last = con.execute("SELECT * FROM insurance_runs ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return {"configured": False, "enabled": False, "endpoint_id": "", "interval_hours": DEFAULT_INTERVAL_HOURS,
                "retention": DEFAULT_RETENTION, "deep_verify": False, "last_run": dict(last) if last else None}
    d = dict(row)
    d["configured"] = True
    d["enabled"] = bool(d["enabled"])
    d["deep_verify"] = bool(d["deep_verify"])
    d["last_run"] = dict(last) if last else None
    try:
        d["endpoint"] = get_sync_endpoint(d["endpoint_id"], db_path=db_path)
    except Exception as exc:
        d["endpoint"] = {"endpoint_id": d["endpoint_id"], "available": False, "error": str(exc)}
    return d


def _insurance_dir(endpoint: dict[str, Any], db_path=None) -> Path:
    root = Path(endpoint["sync_root"]) / "insurance" / device_id(db_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _latest_backup(endpoint: dict[str, Any], db_path=None) -> Path | None:
    root = _insurance_dir(endpoint, db_path=db_path)
    files = [p for p in root.glob("*.mboxenc") if p.is_file()]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def _record_run(*, endpoint_id: str, status: str, backup_path: str = "", backup_sha256: str = "",
                transfer_id: str = "", memory_count: int = 0, attachment_count: int = 0,
                detail: str = "", db_path=None) -> None:
    with _connect(db_path) as con:
        con.execute(
            """INSERT INTO insurance_runs(endpoint_id,status,backup_path,backup_sha256,transfer_id,memory_count,
               attachment_count,detail,created_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            (endpoint_id, status, backup_path, backup_sha256, transfer_id, int(memory_count), int(attachment_count), detail[:4000], utc_now()),
        )


def _is_due(settings: dict[str, Any]) -> bool:
    last = settings.get("last_run") or {}
    if last.get("status") != "ok":
        return True
    age = _age_hours(last.get("created_at"))
    return age is None or age >= float(settings.get("interval_hours") or DEFAULT_INTERVAL_HOURS)


def run_insurance_backup(*, force: bool = False, db_path=None) -> dict[str, Any]:
    settings = insurance_settings(db_path)
    if not settings.get("configured"):
        raise ValueError("automatic insurance is not configured")
    if not settings.get("enabled") and not force:
        return {"ok": True, "skipped": True, "reason": "disabled"}
    if not force and not _is_due(settings):
        return {"ok": True, "skipped": True, "reason": "not_due", "last_run": settings.get("last_run")}
    endpoint_id = str(settings["endpoint_id"])
    ep = get_sync_endpoint(endpoint_id, db_path=db_path)
    if ep.get("encryption_mode") != "e2ee":
        raise ValueError("automatic insurance refuses plaintext sync endpoints")
    if not ep.get("available"):
        raise FileNotFoundError(f"insurance sync folder is unavailable: {ep.get('root_path')}")

    ident = public_identity(db_path)
    try:
        with tempfile.TemporaryDirectory(prefix="memorybox-insurance-") as td:
            plain = Path(td) / "insurance.mbxinsurance"
            built = _create_plain_insurance_archive(plain, db_path=db_path)
            ex = built["transfer"]
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dest_dir = _insurance_dir(ep, db_path=db_path)
            final = dest_dir / f"insurance-{stamp}-{ex['transfer_id']}.mboxenc"
            tmp = final.with_suffix(".mboxenc.tmp")
            enc = encrypt_file_for_recipients(
                plain, tmp,
                recipients=[ident],
                transfer_id=ex["transfer_id"],
                source_device_id=ident["device_id"],
                db_path=db_path,
            )
            tmp.replace(final)
        digest = _sha256_file(final)
        deep_verified = False
        if settings.get("deep_verify"):
            with tempfile.TemporaryDirectory(prefix="memorybox-insurance-postverify-") as vd:
                dec = Path(vd) / "verify.mbxinsurance"
                decrypt_file_for_local_device(final, dec, db_path=db_path)
                inspected = _inspect_plain_insurance_archive(dec, deep_database=True)
                if inspected["memory_count"] != ex["memory_count"] or inspected["attachment_count"] != ex.get("attachment_count", 0):
                    raise ValueError("post-backup verification count mismatch")
                deep_verified = True
        _record_run(endpoint_id=endpoint_id, status="ok", backup_path=str(final), backup_sha256=digest,
                    transfer_id=ex["transfer_id"], memory_count=ex["memory_count"], attachment_count=ex.get("attachment_count", 0),
                    detail=json.dumps({"format": INSURANCE_FORMAT, "version": INSURANCE_VERSION, "recipient_device_ids": enc.get("recipient_device_ids", []), "deep_verified": deep_verified}), db_path=db_path)
        _prune_insurance(ep, int(settings.get("retention") or DEFAULT_RETENTION), db_path=db_path)
        return {"ok": True, "skipped": False, "path": str(final), "sha256": digest, "transfer_id": ex["transfer_id"],
                "memory_count": ex["memory_count"], "attachment_count": ex.get("attachment_count", 0),
                "encrypted": True, "deep_verified": deep_verified, "recipient_device_id": ident["device_id"]}
    except Exception as exc:
        _record_run(endpoint_id=endpoint_id, status="error", detail=str(exc), db_path=db_path)
        raise


def _prune_insurance(endpoint: dict[str, Any], retention: int, db_path=None) -> list[str]:
    root = _insurance_dir(endpoint, db_path=db_path)
    files = sorted((p for p in root.glob("*.mboxenc") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
    removed: list[str] = []
    for p in files[max(2, retention):]:
        try:
            p.unlink(); removed.append(str(p))
        except OSError:
            pass
    return removed


def database_health(db_path=None, *, deep: bool = False) -> dict[str, Any]:
    init_db(db_path)
    db = Path(db_path) if db_path else default_db_path()
    pragma = "integrity_check" if deep else "quick_check"
    with _connect(db_path) as con:
        rows = [str(r[0]) for r in con.execute(f"PRAGMA {pragma}").fetchall()]
        counts = {
            "memories": int(con.execute("SELECT COUNT(*) FROM memories").fetchone()[0]),
            "attachments": int(con.execute("SELECT COUNT(*) FROM attachments").fetchone()[0]),
            "memory_versions": int(con.execute("SELECT COUNT(*) FROM memory_versions").fetchone()[0]),
        }
    ok = rows == ["ok"]
    return {"ok": ok, "check": pragma, "result": rows[:20], "db_path": str(db), "size_bytes": db.stat().st_size if db.exists() else 0, **counts}


def attachment_health(db_path=None, *, deep: bool = False, max_errors: int = 50) -> dict[str, Any]:
    init_db(db_path)
    root = attachment_root(db_path)
    with _connect(db_path) as con:
        rows = [dict(r) for r in con.execute("SELECT sha256,original_name,size_bytes,stored_relpath FROM attachments ORDER BY id").fetchall()]
    missing: list[dict[str, Any]] = []
    corrupt: list[dict[str, Any]] = []
    checked_bytes = 0
    for a in rows:
        fp = root / a["stored_relpath"]
        if not fp.is_file():
            missing.append({"sha256": a["sha256"], "name": a["original_name"]})
            if len(missing) + len(corrupt) >= max_errors: break
            continue
        size = fp.stat().st_size; checked_bytes += size
        if size != int(a["size_bytes"]):
            corrupt.append({"sha256": a["sha256"], "name": a["original_name"], "reason": "size_mismatch"})
        elif deep and _sha256_file(fp) != a["sha256"]:
            corrupt.append({"sha256": a["sha256"], "name": a["original_name"], "reason": "sha256_mismatch"})
        if len(missing) + len(corrupt) >= max_errors: break
    return {"ok": not missing and not corrupt, "deep": bool(deep), "attachment_count": len(rows), "checked_bytes": checked_bytes,
            "missing_count": len(missing), "corrupt_count": len(corrupt), "missing": missing, "corrupt": corrupt}


def _recovery_candidates(db_path=None) -> list[dict[str, Any]]:
    init_db(db_path)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    # Local recovery files created by Memory Box.
    local_root = default_home() / "recovery" if db_path is None else Path(db_path).expanduser().resolve().parent / "recovery"
    if local_root.exists():
        for p in local_root.glob(f"*{RECOVERY_EXT}"):
            if p.is_file():
                seen.add(str(p.resolve()))
                try: candidates.append({"location": "local", **inspect_recovery_kit(p)})
                except Exception as exc: candidates.append({"location": "local", "path": str(p), "valid": False, "error": str(exc)})
    # Encrypted recovery file copies held in configured cloud/sync folders.
    did = device_id(db_path)
    for ep in list_sync_endpoints(db_path=db_path):
        root = Path(ep["sync_root"]) / "recovery" / did
        if not root.exists(): continue
        for p in root.glob(f"*{RECOVERY_EXT}"):
            key = str(p.resolve())
            if key in seen or not p.is_file(): continue
            seen.add(key)
            try: candidates.append({"location": "sync", "endpoint_id": ep["endpoint_id"], "provider": ep["provider"], **inspect_recovery_kit(p)})
            except Exception as exc: candidates.append({"location": "sync", "endpoint_id": ep["endpoint_id"], "provider": ep["provider"], "path": str(p), "valid": False, "error": str(exc)})
    return candidates


def _last_recovery_verification(db_path=None) -> dict[str, Any] | None:
    fp = public_identity(db_path)["fingerprint"]
    with _connect(db_path) as con:
        row = con.execute("SELECT * FROM recovery_events WHERE action='recovery_kit_verified' AND fingerprint=? ORDER BY id DESC LIMIT 1", (fp,)).fetchone()
    return dict(row) if row else None


def verify_latest_insurance(db_path=None) -> dict[str, Any]:
    settings = insurance_settings(db_path)
    if not settings.get("configured"):
        return {"ok": False, "reason": "not_configured"}
    ep = get_sync_endpoint(settings["endpoint_id"], db_path=db_path)
    latest = _latest_backup(ep, db_path=db_path)
    if not latest:
        return {"ok": False, "reason": "no_backup"}
    header = inspect_encrypted_file(latest)["header"]
    with tempfile.TemporaryDirectory(prefix="memorybox-insurance-verify-") as td:
        plain = Path(td) / "verify.mbxinsurance"
        decrypt_file_for_local_device(latest, plain, db_path=db_path)
        info = _inspect_plain_insurance_archive(plain, deep_database=True)
    return {"ok": True, "path": str(latest), "sha256": _sha256_file(latest), "header": header,
            "memory_count": info["memory_count"], "attachment_count": info["attachment_count"],
            "attachment_bytes": info["attachment_bytes"], "database_snapshot_included": info["database_snapshot_included"],
            "attachment_index_included": info["attachment_index_included"], "database_check": info["database_check"], "verified_at": utc_now()}


def disaster_readiness(*, deep: bool = False, max_backup_age_hours: int = DEFAULT_MAX_AGE_HOURS, db_path=None) -> dict[str, Any]:
    dbh = database_health(db_path, deep=deep)
    ath = attachment_health(db_path, deep=deep)
    settings = insurance_settings(db_path)
    recovery = _recovery_candidates(db_path)
    current_ident = public_identity(db_path)
    valid_recovery = [x for x in recovery if x.get("fingerprint") == current_ident.get("fingerprint") and x.get("device_id") == current_ident.get("device_id")]
    offsite_recovery = [x for x in valid_recovery if x.get("location") == "sync"]
    last_ver = _last_recovery_verification(db_path)
    verification_age = _age_hours(last_ver.get("created_at")) if last_ver else None

    endpoint_ok = False; endpoint_e2ee = False; latest_path = None; latest_age = None; backup_verify = None
    if settings.get("configured"):
        ep = settings.get("endpoint") or {}
        endpoint_ok = bool(ep.get("available"))
        endpoint_e2ee = ep.get("encryption_mode") == "e2ee"
        if endpoint_ok:
            latest = _latest_backup(ep, db_path=db_path)
            if latest:
                latest_path = str(latest)
                latest_age = max(0.0, (datetime.now(timezone.utc).timestamp() - latest.stat().st_mtime) / 3600.0)
                try:
                    if deep:
                        backup_verify = verify_latest_insurance(db_path)
                    else:
                        h = inspect_encrypted_file(latest)["header"]
                        local_id = device_id(db_path)
                        recipients = {str(x.get("device_id")) for x in (h.get("recipients") or [])}
                        backup_verify = {"ok": local_id in recipients, "path": str(latest), "header_only": True}
                except Exception as exc:
                    backup_verify = {"ok": False, "error": str(exc)}

    blockers: list[str] = []
    warnings: list[str] = []
    if not dbh["ok"]: blockers.append("SQLite integrity check failed")
    if not ath["ok"]: blockers.append("one or more managed attachments are missing or corrupt")
    if not settings.get("configured") or not settings.get("enabled"): blockers.append("automatic insurance is not enabled")
    if settings.get("configured") and not endpoint_ok: blockers.append("insurance sync endpoint is unavailable")
    if settings.get("configured") and not endpoint_e2ee: blockers.append("insurance endpoint is not E2EE")
    if not latest_path: blockers.append("no encrypted insurance snapshot exists")
    elif latest_age is not None and latest_age > max(1, int(max_backup_age_hours)): warnings.append(f"latest insurance snapshot is {latest_age:.1f} hours old")
    if backup_verify and not backup_verify.get("ok"): blockers.append("latest encrypted insurance snapshot failed verification")
    last_run = settings.get("last_run") or {}
    last_detail = {}
    try: last_detail = json.loads(last_run.get("detail") or "{}")
    except Exception: pass
    if latest_path and not deep and not last_detail.get("deep_verified"):
        warnings.append("latest snapshot has not completed a full decrypt-and-structure verification; run a deep self-test")
    if not valid_recovery: blockers.append("no valid .mbxrecovery file was found")
    elif not offsite_recovery: warnings.append("recovery file exists only locally; keep an encrypted copy off this computer")
    if not last_ver: warnings.append("recovery code has never been verified on this device")
    elif verification_age is not None and verification_age > 24 * 180: warnings.append("recovery-code verification is older than 180 days")

    if blockers:
        status = "RED"
    elif warnings:
        status = "YELLOW"
    else:
        status = "GREEN"
    recoverable = bool(not blockers and latest_path and valid_recovery)
    return {
        "status": status,
        "recoverable_if_recovery_code_available": recoverable,
        "checked_at": utc_now(),
        "deep": bool(deep),
        "database": dbh,
        "attachments": ath,
        "insurance": {"settings": settings, "latest_backup_path": latest_path, "latest_backup_age_hours": latest_age, "verification": backup_verify},
        "recovery": {"files_found": recovery, "valid_count": len(valid_recovery), "offsite_count": len(offsite_recovery), "last_code_verification": last_ver},
        "blockers": blockers,
        "warnings": warnings,
        "note": "Automatic checks cannot prove that you still possess the recovery code. Use a local recovery-code verification drill to test that factor without exposing the code to an AI agent.",
    }


class InsuranceMonitor:
    def __init__(self, interval_seconds: float = 300.0, db_path=None):
        self.interval_seconds = max(60.0, float(interval_seconds))
        self.db_path = db_path
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> "InsuranceMonitor":
        if self._thread and self._thread.is_alive():
            return self
        self._thread = threading.Thread(target=self._run, name="MemoryBoxInsuranceMonitor", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                st = insurance_settings(self.db_path)
                if st.get("configured") and st.get("enabled") and _is_due(st):
                    try:
                        run_insurance_backup(db_path=self.db_path)
                    except Exception:
                        pass
            except Exception:
                pass
            self._stop.wait(self.interval_seconds)
