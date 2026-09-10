from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import shutil
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .crypto import export_device_identity_secret, install_device_identity_secret, public_identity
from .db import _connect, default_home, init_db, utc_now

RECOVERY_FORMAT = "memorybox-recovery"
RECOVERY_VERSION = 1
RECOVERY_EXT = ".mbxrecovery"
CODE_PREFIX = "MBR1"
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _normalize_code(code: str) -> str:
    text = "".join(ch for ch in str(code).upper() if ch.isalnum())
    if text.startswith(CODE_PREFIX):
        text = text[len(CODE_PREFIX):]
    if len(text) < 26:
        raise ValueError("recovery code is too short")
    return text


def generate_recovery_code() -> str:
    # 160 bits of entropy; the prefix is format/version metadata, not secret material.
    raw = base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
    groups = [raw[i:i+4] for i in range(0, len(raw), 4)]
    return CODE_PREFIX + "-" + "-".join(groups)


def _derive_key(code: str, salt: bytes, *, n: int = SCRYPT_N, r: int = SCRYPT_R, p: int = SCRYPT_P) -> bytes:
    normalized = _normalize_code(code).encode("ascii")
    return Scrypt(salt=salt, length=32, n=int(n), r=int(r), p=int(p)).derive(normalized)


def _record_event(action: str, fingerprint: str, file_sha256: str = "", detail: str = "", db_path=None) -> None:
    init_db(db_path)
    with _connect(db_path) as con:
        con.execute(
            "INSERT INTO recovery_events(action,fingerprint,recovery_file_sha256,detail,created_at) VALUES(?,?,?,?,?)",
            (action, fingerprint, file_sha256, detail, utc_now()),
        )


def create_recovery_kit(output_path: str | os.PathLike[str], *, recovery_code: str | None = None, db_path=None) -> dict[str, Any]:
    """Create an encrypted recovery file. The recovery code is returned once and never stored in the DB/file."""
    ident = public_identity(db_path)
    secret_payload = export_device_identity_secret(db_path)
    code = recovery_code or generate_recovery_code()
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    header = {
        "format": RECOVERY_FORMAT,
        "version": RECOVERY_VERSION,
        "created_at": utc_now(),
        "device_id": ident["device_id"],
        "public_key": ident["public_key"],
        "fingerprint": ident["fingerprint"],
        "kdf": {"name": "scrypt", "n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P, "salt": _b64(salt)},
        "cipher": {"name": "AES-256-GCM", "nonce": _b64(nonce)},
    }
    key = _derive_key(code, salt)
    ciphertext = AESGCM(key).encrypt(nonce, _canonical(secret_payload), _canonical(header))
    doc = {**header, "encrypted_identity": _b64(ciphertext)}
    out = Path(output_path).expanduser().resolve()
    if out.suffix.lower() != RECOVERY_EXT:
        out = out.with_suffix(RECOVERY_EXT)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(out)
    try:
        os.chmod(out, 0o600)
    except OSError:
        pass
    digest = _sha256_file(out)
    _record_event("recovery_kit_created", ident["fingerprint"], digest, str(out), db_path=db_path)
    return {
        "ok": True,
        "path": str(out),
        "recovery_code": code,
        "fingerprint": ident["fingerprint"],
        "device_id": ident["device_id"],
        "sha256": digest,
        "warning": "Store the recovery file and recovery code separately. Anyone with both can recover this device identity.",
    }


def inspect_recovery_kit(path: str | os.PathLike[str]) -> dict[str, Any]:
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(p)
    if p.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("recovery file is unexpectedly large")
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("format") != RECOVERY_FORMAT or int(doc.get("version", 0)) != RECOVERY_VERSION:
        raise ValueError("unsupported Memory Box recovery format")
    kdf = doc.get("kdf") or {}; cipher = doc.get("cipher") or {}
    if kdf.get("name") != "scrypt" or cipher.get("name") != "AES-256-GCM":
        raise ValueError("unsupported recovery cryptography")
    n, r, par = int(kdf.get("n", 0)), int(kdf.get("r", 0)), int(kdf.get("p", 0))
    if n < 2**14 or n > 2**20 or r < 1 or r > 64 or par < 1 or par > 16:
        raise ValueError("unsafe or unsupported recovery KDF parameters")
    _unb64(str(kdf.get("salt") or "")); _unb64(str(cipher.get("nonce") or "")); _unb64(str(doc.get("encrypted_identity") or ""))
    return {
        "path": str(p),
        "format": doc["format"],
        "version": int(doc["version"]),
        "created_at": doc.get("created_at", ""),
        "device_id": doc.get("device_id", ""),
        "public_key": doc.get("public_key", ""),
        "fingerprint": doc.get("fingerprint", ""),
        "sha256": _sha256_file(p),
    }


def restore_recovery_kit(path: str | os.PathLike[str], recovery_code: str, *, replace_existing: bool = False, db_path=None) -> dict[str, Any]:
    p = Path(path).expanduser().resolve()
    meta = inspect_recovery_kit(p)
    doc = json.loads(p.read_text(encoding="utf-8"))
    header = {k: doc[k] for k in ("format", "version", "created_at", "device_id", "public_key", "fingerprint", "kdf", "cipher")}
    salt = _unb64(doc["kdf"]["salt"]); nonce = _unb64(doc["cipher"]["nonce"])
    key = _derive_key(recovery_code, salt, n=int(doc["kdf"]["n"]), r=int(doc["kdf"]["r"]), p=int(doc["kdf"]["p"]))
    try:
        plaintext = AESGCM(key).decrypt(nonce, _unb64(doc["encrypted_identity"]), _canonical(header))
    except InvalidTag as exc:
        raise PermissionError("recovery code is incorrect or the recovery file was modified") from exc
    payload = json.loads(plaintext.decode("utf-8"))
    if str(payload.get("device_id") or "") != str(doc.get("device_id") or ""):
        raise ValueError("recovery identity device ID mismatch")
    result = install_device_identity_secret(payload, db_path=db_path, replace_existing=replace_existing)
    restored = public_identity(db_path)
    if restored["public_key"] != doc.get("public_key") or restored["fingerprint"] != doc.get("fingerprint"):
        raise ValueError("restored identity does not match recovery file metadata")
    _record_event("recovery_kit_restored", restored["fingerprint"], meta["sha256"], f"replaced={bool(result.get('replaced'))}", db_path=db_path)
    return {"ok": True, **result, "fingerprint": restored["fingerprint"], "device_id": restored["device_id"], "recovery_file_sha256": meta["sha256"]}


def recovery_status(db_path=None) -> dict[str, Any]:
    init_db(db_path)
    ident = public_identity(db_path)
    with _connect(db_path) as con:
        row = con.execute("SELECT action,fingerprint,recovery_file_sha256,detail,created_at FROM recovery_events ORDER BY id DESC LIMIT 1").fetchone()
        created = con.execute("SELECT COUNT(*) FROM recovery_events WHERE action='recovery_kit_created'").fetchone()[0]
        restored = con.execute("SELECT COUNT(*) FROM recovery_events WHERE action='recovery_kit_restored'").fetchone()[0]
        verified = con.execute("SELECT COUNT(*) FROM recovery_events WHERE action='recovery_kit_verified'").fetchone()[0]
    return {
        "device_id": ident["device_id"],
        "fingerprint": ident["fingerprint"],
        "recovery_kits_created": int(created),
        "recoveries_performed": int(restored),
        "recovery_code_verifications": int(verified),
        "last_recovery_event": dict(row) if row else None,
        "recommendation": "Keep at least one .mbxrecovery file and its recovery code in separate locations.",
    }


def backup_recovery_file_to_sync(recovery_path: str | os.PathLike[str], endpoint_id: str, *, db_path=None) -> dict[str, Any]:
    """Copy the already-encrypted recovery file into a configured sync folder. Never stores the recovery code."""
    from .sync import get_sync_endpoint

    src = Path(recovery_path).expanduser().resolve()
    meta = inspect_recovery_kit(src)
    ep = get_sync_endpoint(endpoint_id, db_path=db_path)
    root = Path(ep["sync_root"]) / "recovery" / str(meta["device_id"])
    root.mkdir(parents=True, exist_ok=True)
    name = f"MemoryBox-Recovery-{str(meta['device_id'])[:8]}-{meta['sha256'][:12]}{RECOVERY_EXT}"
    dst = root / name
    if not dst.exists() or _sha256_file(dst) != meta["sha256"]:
        tmp = dst.with_suffix(dst.suffix + ".tmp")
        shutil.copyfile(src, tmp)
        tmp.replace(dst)
    _record_event("recovery_kit_cloud_backup", meta["fingerprint"], meta["sha256"], f"endpoint={endpoint_id}", db_path=db_path)
    return {"ok": True, "endpoint_id": endpoint_id, "provider": ep["provider"], "path": str(dst), "sha256": meta["sha256"], "recovery_code_stored": False}


def verify_recovery_kit(path: str | os.PathLike[str], recovery_code: str, *, db_path=None) -> dict[str, Any]:
    """Verify a recovery file/code pair without installing or replacing any device identity."""
    p = Path(path).expanduser().resolve()
    meta = inspect_recovery_kit(p)
    doc = json.loads(p.read_text(encoding="utf-8"))
    header = {k: doc[k] for k in ("format", "version", "created_at", "device_id", "public_key", "fingerprint", "kdf", "cipher")}
    salt = _unb64(doc["kdf"]["salt"]); nonce = _unb64(doc["cipher"]["nonce"])
    key = _derive_key(recovery_code, salt, n=int(doc["kdf"]["n"]), r=int(doc["kdf"]["r"]), p=int(doc["kdf"]["p"]))
    try:
        plaintext = AESGCM(key).decrypt(nonce, _unb64(doc["encrypted_identity"]), _canonical(header))
    except InvalidTag as exc:
        raise PermissionError("recovery code is incorrect or the recovery file was modified") from exc
    payload = json.loads(plaintext.decode("utf-8"))
    if str(payload.get("device_id") or "") != str(doc.get("device_id") or ""):
        raise ValueError("recovery identity device ID mismatch")
    if str(payload.get("public_key") or "") != str(doc.get("public_key") or ""):
        raise ValueError("recovery identity public key mismatch")
    current = public_identity(db_path)
    matches_current = current["public_key"] == doc.get("public_key") and current["device_id"] == doc.get("device_id")
    _record_event("recovery_kit_verified", str(doc.get("fingerprint") or ""), meta["sha256"], f"matches_current={matches_current}", db_path=db_path)
    return {"ok": True, "device_id": doc.get("device_id"), "fingerprint": doc.get("fingerprint"),
            "matches_current_identity": matches_current, "recovery_file_sha256": meta["sha256"],
            "verified_at": utc_now(), "recovery_code_stored": False}
