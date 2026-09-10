from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import socket
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .transfer import device_id, import_transfer_bundle, inspect_transfer_bundle
from .crypto import MAGIC, decrypt_file_for_local_device, encrypt_file_for_recipients, public_identity

DISCOVERY_PORT = 18768
PAIR_TTL_SECONDS = 300
_ACTIVE = None
_LOCK = threading.Lock()


def _device_name() -> str:
    return os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or socket.gethostname() or "MemoryBox device"


def _local_ips() -> list[str]:
    ips = {"127.0.0.1"}
    try:
        for x in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(x[4][0])
    except Exception:
        pass
    return sorted(ips)


class _Receiver:
    def __init__(self, host="0.0.0.0", port=0, ttl=PAIR_TTL_SECONDS, db_path=None):
        self.code = f"{secrets.randbelow(1_000_000):06d}"
        self.expires_at = time.time() + max(30, int(ttl))
        self.db_path = db_path
        self.server = ThreadingHTTPServer((host, int(port)), self._handler_class())
        self.port = int(self.server.server_address[1])
        self.http_thread = threading.Thread(target=self.server.serve_forever, daemon=True, name="MemoryBoxLANReceiver")
        self.udp_stop = threading.Event()
        self.udp_thread = threading.Thread(target=self._udp_loop, daemon=True, name="MemoryBoxLANDiscovery")

    def _handler_class(self):
        outer = self
        class H(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def _json(self, obj, status=200):
                data=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
            def do_GET(self):
                if self.path == '/ping':
                    ident=public_identity(outer.db_path)
                    return self._json({"ok":True,"device_id":device_id(outer.db_path),"device_name":_device_name(),"expires_at":outer.expires_at,"e2ee_public_key":ident["public_key"],"e2ee_fingerprint":ident["fingerprint"],"e2ee_supported":True})
                return self._json({"error":"not found"},404)
            def do_POST(self):
                if self.path != '/receive': return self._json({"error":"not found"},404)
                if time.time() > outer.expires_at: return self._json({"error":"pairing window expired"},403)
                n=int(self.headers.get('Content-Length','0'))
                if n <= 0 or n > 2*1024*1024*1024: return self._json({"error":"invalid package size"},413)
                raw=self.rfile.read(n)
                supplied=self.headers.get('X-MemoryBox-Auth','')
                expected=hmac.new(outer.code.encode(),raw,hashlib.sha256).hexdigest()
                if not hmac.compare_digest(supplied,expected): return self._json({"error":"invalid pairing code/authentication"},403)
                suffix = '.mboxenc' if raw.startswith(MAGIC) else '.mboxpack'
                with tempfile.NamedTemporaryFile(suffix=suffix,delete=False) as tf:
                    tf.write(raw); temp=tf.name
                dec = None
                try:
                    import_path=temp
                    if suffix == '.mboxenc':
                        dec=temp+'.decrypted.mboxpack'
                        decrypt_file_for_local_device(temp,dec,db_path=outer.db_path)
                        import_path=dec
                    else:
                        raise ValueError('Memory Box v0.9 LAN requires E2EE; plaintext LAN packages are rejected')
                    result=import_transfer_bundle(import_path,db_path=outer.db_path)
                    return self._json({"ok":True,"encrypted":True,"result":result})
                except Exception as exc:
                    return self._json({"error":str(exc)},400)
                finally:
                    try: os.unlink(temp)
                    except OSError: pass
                    if dec:
                        try: os.unlink(dec)
                        except OSError: pass
        return H

    def start(self):
        self.http_thread.start(); self.udp_thread.start(); return self

    def stop(self):
        self.udp_stop.set(); self.server.shutdown(); self.server.server_close()

    def status(self):
        return {"active": time.time() <= self.expires_at, "code": self.code,
                "port": self.port, "expires_in_seconds": max(0,int(self.expires_at-time.time())),
                "device_id": device_id(self.db_path), "device_name": _device_name(), "ips": _local_ips(),
                "security": "End-to-end encrypted with X25519 + AES-256-GCM and authenticated with a one-time pairing code.",
                "e2ee": public_identity(self.db_path)}

    def _udp_loop(self):
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:
            s.bind(('',DISCOVERY_PORT)); s.settimeout(0.5)
            while not self.udp_stop.is_set() and time.time() <= self.expires_at:
                try: data,addr=s.recvfrom(1024)
                except socket.timeout: continue
                except OSError: break
                if data != b'MEMORYBOX_DISCOVER_V1': continue
                ident=public_identity(self.db_path)
                payload=json.dumps({"magic":"MEMORYBOX_PEER_V1","device_id":device_id(self.db_path),"device_name":_device_name(),"port":self.port,"e2ee_public_key":ident["public_key"],"e2ee_fingerprint":ident["fingerprint"],"e2ee_supported":True}).encode()
                try: s.sendto(payload,addr)
                except OSError: pass
        finally: s.close()


def start_pairing(*, port: int = 0, ttl: int = PAIR_TTL_SECONDS, db_path=None) -> dict[str, Any]:
    global _ACTIVE
    with _LOCK:
        if _ACTIVE is not None:
            try: _ACTIVE.stop()
            except Exception: pass
        _ACTIVE = _Receiver(port=port,ttl=ttl,db_path=db_path).start()
        return _ACTIVE.status()


def pairing_status() -> dict[str, Any]:
    with _LOCK:
        if _ACTIVE is None: return {"active":False}
        return _ACTIVE.status()


def stop_pairing() -> dict[str, Any]:
    global _ACTIVE
    with _LOCK:
        if _ACTIVE is not None:
            try: _ACTIVE.stop()
            finally: _ACTIVE=None
    return {"ok":True,"active":False}


def discover_peers(timeout: float = 1.2) -> list[dict[str, Any]]:
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1); s.settimeout(max(0.2,float(timeout)))
    found={}
    try:
        s.bind(('',0)); s.sendto(b'MEMORYBOX_DISCOVER_V1',('<broadcast>',DISCOVERY_PORT)); end=time.time()+timeout
        while time.time()<end:
            try: data,addr=s.recvfrom(4096)
            except socket.timeout: break
            try: d=json.loads(data.decode())
            except Exception: continue
            if d.get('magic')!='MEMORYBOX_PEER_V1': continue
            d['host']=addr[0]; found[(d.get('device_id'),addr[0],d.get('port'))]=d
    except OSError:
        pass
    finally: s.close()
    return list(found.values())


def send_pack(host: str, port: int, code: str, package_path: str | os.PathLike[str], *, timeout: float = 120.0, db_path=None) -> dict[str, Any]:
    p=Path(package_path).expanduser().resolve()
    if not p.is_file(): raise FileNotFoundError(p)
    # Query the receiver identity inside the short-lived pairing window. The
    # one-time code authenticates the transfer; the X25519 key encrypts it.
    try:
        with urllib.request.urlopen(f'http://{host}:{int(port)}/ping',timeout=min(timeout,10)) as r:
            peer=json.loads(r.read())
    except Exception as exc:
        raise RuntimeError(f"LAN peer identity lookup failed: {exc}") from exc
    if not peer.get('e2ee_public_key'):
        raise RuntimeError('LAN peer does not support Memory Box E2EE')
    meta=inspect_transfer_bundle(p); tid=str(meta['manifest'].get('transfer_id') or '')
    if not tid: raise ValueError('package has no transfer_id')
    with tempfile.TemporaryDirectory(prefix='memorybox-lan-send-') as td:
        enc=Path(td)/f'{tid}.mboxenc'
        encrypt_file_for_recipients(p,enc,recipients=[{'device_id':str(peer['device_id']),'public_key':str(peer['e2ee_public_key']),'fingerprint':str(peer.get('e2ee_fingerprint') or '')}],transfer_id=tid,source_device_id=device_id(db_path),db_path=db_path)
        raw=enc.read_bytes()
    auth=hmac.new(str(code).encode(),raw,hashlib.sha256).hexdigest()
    req=urllib.request.Request(f'http://{host}:{int(port)}/receive',data=raw,method='POST',headers={
        'Content-Type':'application/octet-stream','X-MemoryBox-Auth':auth,'Content-Length':str(len(raw))})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            result=json.loads(r.read()); result['e2ee']=True; result['peer_fingerprint']=peer.get('e2ee_fingerprint'); return result
    except Exception as exc:
        raise RuntimeError(f"LAN transfer failed: {exc}") from exc
