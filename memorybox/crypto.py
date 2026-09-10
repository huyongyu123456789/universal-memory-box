from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import struct
from pathlib import Path
from typing import Any, Iterable

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
except Exception as exc:  # pragma: no cover - exercised only on broken installs
    raise RuntimeError(
        "Memory Box E2EE requires the 'cryptography' package. Reinstall Memory Box v0.9+ or run: pip install cryptography"
    ) from exc

from .db import _connect, default_home, init_db, utc_now
from .transfer import device_id

E2EE_FORMAT = "memorybox-e2ee"
E2EE_VERSION = 1
MAGIC = b"MEMORYBOXE2EE1\n"
HEADER_LEN = struct.Struct(">Q")
TAG_LEN = 16
CHUNK = 1024 * 1024


def _home_for(db_path=None) -> Path:
    if db_path is None:
        return default_home()
    return Path(db_path).expanduser().resolve().parent


def _keys_dir(db_path=None) -> Path:
    p = _home_for(db_path) / "keys"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _identity_path(db_path=None) -> Path:
    return _keys_dir(db_path) / "device-x25519.json"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _fingerprint(raw_public: bytes) -> str:
    h = hashlib.sha256(raw_public).hexdigest().upper()
    return ":".join(h[i:i+4] for i in range(0, 32, 4))



def fingerprint_public_key(public_key: str) -> str:
    return _fingerprint(_unb64(public_key))

def ensure_device_identity(db_path=None) -> dict[str, Any]:
    path = _identity_path(db_path)
    if path.exists():
        obj = json.loads(path.read_text(encoding="utf-8"))
        private_raw = _unb64(obj["private_key"])
        priv = X25519PrivateKey.from_private_bytes(private_raw)
    else:
        priv = X25519PrivateKey.generate()
        private_raw = priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
        pub_raw = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        obj = {
            "format": "memorybox-device-key",
            "version": 1,
            "device_id": device_id(db_path),
            "created_at": utc_now(),
            "private_key": _b64(private_raw),
            "public_key": _b64(pub_raw),
            "fingerprint": _fingerprint(pub_raw),
        }
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    pub_raw = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {
        "device_id": device_id(db_path),
        "public_key": _b64(pub_raw),
        "fingerprint": _fingerprint(pub_raw),
        "key_path": str(path),
        "algorithm": "X25519",
    }


def public_identity(db_path=None) -> dict[str, Any]:
    d = ensure_device_identity(db_path)
    return {k: d[k] for k in ("device_id", "public_key", "fingerprint", "algorithm")}


def _private_key(db_path=None) -> X25519PrivateKey:
    ensure_device_identity(db_path)
    obj = json.loads(_identity_path(db_path).read_text(encoding="utf-8"))
    return X25519PrivateKey.from_private_bytes(_unb64(obj["private_key"]))




def export_device_identity_secret(db_path=None) -> dict[str, Any]:
    """Return device private identity material for encrypted disaster-recovery backup only."""
    ensure_device_identity(db_path)
    obj = json.loads(_identity_path(db_path).read_text(encoding="utf-8"))
    priv = X25519PrivateKey.from_private_bytes(_unb64(obj["private_key"]))
    pub_raw = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {
        "format": "memorybox-device-secret",
        "version": 1,
        "device_id": device_id(db_path),
        "created_at": obj.get("created_at") or utc_now(),
        "private_key": _b64(priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())),
        "public_key": _b64(pub_raw),
        "fingerprint": _fingerprint(pub_raw),
    }


def install_device_identity_secret(payload: dict[str, Any], *, db_path=None, replace_existing: bool = False) -> dict[str, Any]:
    """Install a recovered X25519 identity. Existing non-empty boxes require explicit replacement."""
    if payload.get("format") != "memorybox-device-secret" or int(payload.get("version", 0)) != 1:
        raise ValueError("unsupported recovered device-secret format")
    private_raw = _unb64(str(payload.get("private_key") or ""))
    if len(private_raw) != 32:
        raise ValueError("invalid recovered X25519 private key")
    priv = X25519PrivateKey.from_private_bytes(private_raw)
    pub_raw = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    public_key = _b64(pub_raw); fingerprint = _fingerprint(pub_raw)
    if payload.get("public_key") and payload.get("public_key") != public_key:
        raise ValueError("recovered public key does not match private key")
    if payload.get("fingerprint") and payload.get("fingerprint") != fingerprint:
        raise ValueError("recovered fingerprint does not match private key")
    recovered_device_id = str(payload.get("device_id") or "").strip()
    if not recovered_device_id:
        raise ValueError("recovered identity has no device ID")

    init_db(db_path)
    path = _identity_path(db_path)
    backup_path = None; replaced = False
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
        current_priv = X25519PrivateKey.from_private_bytes(_unb64(current["private_key"]))
        current_pub = current_priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        if current_pub == pub_raw:
            with _connect(db_path) as con:
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('device_id',?)", (recovered_device_id,))
            return {"installed": True, "replaced": False, "idempotent": True, "key_path": str(path), "backup_path": None}
        with _connect(db_path) as con:
            memories = int(con.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
            endpoints = int(con.execute("SELECT COUNT(*) FROM sync_endpoints").fetchone()[0])
        if (memories or endpoints) and not replace_existing:
            raise FileExistsError("this Memory Box already has a different active device identity; pass replace_existing only after backing it up")
        stamp = utc_now().replace(":", "").replace("-", "")
        backup_path = path.with_name(f"device-x25519.pre-recovery-{stamp}.json")
        backup_path.write_bytes(path.read_bytes())
        try:
            os.chmod(backup_path, 0o600)
        except OSError:
            pass
        replaced = True

    obj = {
        "format": "memorybox-device-key",
        "version": 1,
        "device_id": recovered_device_id,
        "created_at": payload.get("created_at") or utc_now(),
        "private_key": _b64(private_raw),
        "public_key": public_key,
        "fingerprint": fingerprint,
        "restored_at": utc_now(),
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    with _connect(db_path) as con:
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('device_id',?)", (recovered_device_id,))
    return {"installed": True, "replaced": replaced, "idempotent": False, "key_path": str(path), "backup_path": str(backup_path) if backup_path else None}

def _derive_wrap_key(shared: bytes, *, transfer_id: str, recipient_device_id: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=hashlib.sha256(transfer_id.encode("utf-8")).digest(),
        info=("MemoryBox E2EE wrap v1|" + recipient_device_id).encode("utf-8"),
    ).derive(shared)


def _canonical_header(header: dict[str, Any]) -> bytes:
    return json.dumps(header, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def encrypt_file_for_recipients(
    input_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    *,
    recipients: Iterable[dict[str, str]],
    transfer_id: str,
    source_device_id: str | None = None,
    db_path=None,
) -> dict[str, Any]:
    src = Path(input_path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(src)
    unique: dict[str, dict[str, str]] = {}
    for r in recipients:
        did = str(r.get("device_id") or "").strip()
        pub = str(r.get("public_key") or "").strip()
        if did and pub:
            unique[did] = {"device_id": did, "public_key": pub, "fingerprint": str(r.get("fingerprint") or "")}
    if not unique:
        raise ValueError("no E2EE recipients supplied")

    content_key = secrets.token_bytes(32)
    content_nonce = secrets.token_bytes(12)
    sender_priv = _private_key(db_path)
    sender_ident = public_identity(db_path)
    wrapped: list[dict[str, str]] = []
    for r in sorted(unique.values(), key=lambda x: x["device_id"]):
        recipient_pub = X25519PublicKey.from_public_bytes(_unb64(r["public_key"]))
        shared = sender_priv.exchange(recipient_pub)
        kek = _derive_wrap_key(shared, transfer_id=transfer_id, recipient_device_id=r["device_id"])
        wrap_nonce = secrets.token_bytes(12)
        aad = (transfer_id + "|" + r["device_id"]).encode("utf-8")
        wrapped_key = AESGCM(kek).encrypt(wrap_nonce, content_key, aad)
        wrapped.append({
            "device_id": r["device_id"],
            "fingerprint": r.get("fingerprint") or _fingerprint(_unb64(r["public_key"])),
            "nonce": _b64(wrap_nonce),
            "wrapped_key": _b64(wrapped_key),
        })

    header = {
        "format": E2EE_FORMAT,
        "version": E2EE_VERSION,
        "created_at": utc_now(),
        "transfer_id": str(transfer_id),
        "source_device_id": str(source_device_id or device_id(db_path)),
        "plaintext_size": src.stat().st_size,
        "cipher": "AES-256-GCM",
        "key_agreement": "X25519 authenticated device-to-device",
        "kdf": "HKDF-SHA256",
        "content_nonce": _b64(content_nonce),
        "sender_public_key": sender_ident["public_key"],
        "sender_fingerprint": sender_ident["fingerprint"],
        "recipients": wrapped,
    }
    header_bytes = _canonical_header(header)
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    encryptor = Cipher(algorithms.AES(content_key), modes.GCM(content_nonce)).encryptor()
    encryptor.authenticate_additional_data(header_bytes)
    with src.open("rb") as fin, tmp.open("wb") as fout:
        fout.write(MAGIC)
        fout.write(HEADER_LEN.pack(len(header_bytes)))
        fout.write(header_bytes)
        while True:
            chunk = fin.read(CHUNK)
            if not chunk:
                break
            fout.write(encryptor.update(chunk))
        fout.write(encryptor.finalize())
        fout.write(encryptor.tag)
    tmp.replace(out)
    return {
        "ok": True,
        "path": str(out),
        "format": E2EE_FORMAT,
        "version": E2EE_VERSION,
        "transfer_id": transfer_id,
        "source_device_id": header["source_device_id"],
        "recipient_device_ids": [r["device_id"] for r in wrapped],
        "plaintext_size": header["plaintext_size"],
        "ciphertext_size": out.stat().st_size,
    }


def inspect_encrypted_file(path: str | os.PathLike[str]) -> dict[str, Any]:
    p = Path(path).expanduser().resolve()
    with p.open("rb") as f:
        if f.read(len(MAGIC)) != MAGIC:
            raise ValueError("not a Memory Box E2EE package")
        raw = f.read(HEADER_LEN.size)
        if len(raw) != HEADER_LEN.size:
            raise ValueError("truncated E2EE header")
        n = HEADER_LEN.unpack(raw)[0]
        if n <= 0 or n > 4 * 1024 * 1024:
            raise ValueError("invalid E2EE header length")
        hb = f.read(n)
        if len(hb) != n:
            raise ValueError("truncated E2EE header")
        header = json.loads(hb.decode("utf-8"))
    if header.get("format") != E2EE_FORMAT or int(header.get("version", 0)) != E2EE_VERSION:
        raise ValueError("unsupported Memory Box E2EE format")
    return {"header": header, "header_bytes": hb, "path": str(p)}


def decrypt_file_for_local_device(input_path: str | os.PathLike[str], output_path: str | os.PathLike[str], *, expected_sender_public_key: str | None = None, db_path=None) -> dict[str, Any]:
    meta = inspect_encrypted_file(input_path)
    header = meta["header"]
    hb = meta["header_bytes"]
    local = public_identity(db_path)
    recipient = next((r for r in header.get("recipients", []) if r.get("device_id") == local["device_id"]), None)
    if recipient is None:
        # device_id can be regenerated only if the database identity changed; fingerprint is a safe fallback.
        recipient = next((r for r in header.get("recipients", []) if r.get("fingerprint") == local["fingerprint"]), None)
    if recipient is None:
        raise PermissionError("encrypted package is not addressed to this Memory Box device")

    sender_public_key = str(header.get("sender_public_key") or "")
    if not sender_public_key:
        raise ValueError("encrypted package has no sender public key")
    if expected_sender_public_key and sender_public_key != expected_sender_public_key:
        raise PermissionError("encrypted package sender key does not match the trusted device key")
    sender_raw = _unb64(sender_public_key)
    if header.get("sender_fingerprint") and header.get("sender_fingerprint") != _fingerprint(sender_raw):
        raise ValueError("encrypted package sender fingerprint mismatch")
    priv = _private_key(db_path)
    sender_pub = X25519PublicKey.from_public_bytes(sender_raw)
    shared = priv.exchange(sender_pub)
    kek = _derive_wrap_key(shared, transfer_id=header["transfer_id"], recipient_device_id=recipient["device_id"])
    aad = (header["transfer_id"] + "|" + recipient["device_id"]).encode("utf-8")
    content_key = AESGCM(kek).decrypt(_unb64(recipient["nonce"]), _unb64(recipient["wrapped_key"]), aad)

    src = Path(input_path).expanduser().resolve()
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    plain_size = int(header["plaintext_size"])
    prefix = len(MAGIC) + HEADER_LEN.size + len(hb)
    expected_size = prefix + plain_size + TAG_LEN
    if src.stat().st_size != expected_size:
        raise ValueError("encrypted package size mismatch")
    with src.open("rb") as fin:
        fin.seek(prefix + plain_size)
        tag = fin.read(TAG_LEN)
        if len(tag) != TAG_LEN:
            raise ValueError("truncated E2EE authentication tag")
        fin.seek(prefix)
        decryptor = Cipher(algorithms.AES(content_key), modes.GCM(_unb64(header["content_nonce"]), tag)).decryptor()
        decryptor.authenticate_additional_data(hb)
        tmp = out.with_suffix(out.suffix + ".tmp")
        remaining = plain_size
        try:
            with tmp.open("wb") as fout:
                while remaining:
                    chunk = fin.read(min(CHUNK, remaining))
                    if not chunk:
                        raise ValueError("truncated encrypted payload")
                    remaining -= len(chunk)
                    fout.write(decryptor.update(chunk))
                fout.write(decryptor.finalize())
            tmp.replace(out)
        except Exception:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
    return {
        "ok": True,
        "path": str(out),
        "transfer_id": header["transfer_id"],
        "source_device_id": header["source_device_id"],
        "recipient_device_id": recipient["device_id"],
        "plaintext_size": plain_size,
    }
