from __future__ import annotations

import base64
import json
import re
import tempfile
import threading
import urllib.parse
import webbrowser
import sys
from pathlib import Path
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from . import __version__
from .agents import auto_link_once, connect_agent, connect_all_detected, scan_agents
from .categories import CATEGORY_LABELS
from .attachments import add_attachment_bytes, get_attachment, list_attachments
from .db import append_memory, category_counts, compose_context, default_home, get_memory, init_db, list_memories, related_memories, save_memory, set_flag
from .transfer import export_transfer_bundle, import_transfer_bundle, inspect_transfer_bundle
from .sync import PROVIDERS, SyncMonitor, configure_sync_folder, detect_sync_folders, list_sync_devices, list_sync_endpoints, publish_to_sync, receive_from_sync, remove_sync_endpoint, trust_sync_device, revoke_sync_device, sync_security_status, set_sync_encryption
from .lan import discover_peers, pairing_status, send_pack, start_pairing, stop_pairing
from .crypto import public_identity, decrypt_file_for_local_device, inspect_encrypted_file
from .recovery import create_recovery_kit, inspect_recovery_kit, recovery_status, restore_recovery_kit, backup_recovery_file_to_sync, verify_recovery_kit
from .insurance import InsuranceMonitor, configure_insurance, disable_insurance, insurance_settings, run_insurance_backup, disaster_readiness, verify_latest_insurance, restore_latest_insurance, list_insurance_snapshots

from .ui import HTML


def _brand_icon_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    p = base / "assets" / "icons" / "master.png"
    if p.exists():
        return p
    return Path(__file__).resolve().parents[1] / "assets" / "icons" / "master.png"


class Handler(BaseHTTPRequestHandler):
    def _send(self,obj:Any,status=200,ctype="application/json; charset=utf-8"):
        data=(obj if isinstance(obj,(bytes,bytearray)) else (obj.encode() if isinstance(obj,str) else json.dumps(obj,ensure_ascii=False).encode()))
        self.send_response(status); self.send_header("Content-Type",ctype); self.send_header("Content-Length",str(len(data))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(data)
    def log_message(self,*args): pass
    def _json(self):
        n=int(self.headers.get("Content-Length","0"))
        if n > 96*1024*1024: raise ValueError("request body is too large")
        return json.loads(self.rfile.read(n) or b"{}")
    def do_GET(self):
        try:
            u=urllib.parse.urlparse(self.path); p=u.path; q=urllib.parse.parse_qs(u.query)
            if p=="/": return self._send(HTML.replace('__CATEGORIES__', json.dumps(CATEGORY_LABELS, ensure_ascii=False)).replace('__VERSION__', __version__),ctype="text/html; charset=utf-8")
            if p=="/brand-icon.png":
                fp=_brand_icon_path()
                if not fp.is_file(): return self._send({"error":"brand icon not found"},404)
                return self._send(fp.read_bytes(),ctype="image/png")
            if p=="/api/health": return self._send({"ok":True,"name":"Memory Box","version":__version__})
            if p=="/api/categories": return self._send(category_counts())
            if p=="/api/agents": return self._send(scan_agents())
            if p=="/api/device/identity": return self._send(public_identity())
            if p=="/api/recovery/status": return self._send(recovery_status())
            if p=="/api/insurance/status": return self._send(insurance_settings())
            if p=="/api/insurance/health": return self._send(disaster_readiness(deep=(q.get('deep') or ['0'])[0] in {'1','true','yes'}))
            if p=="/api/insurance/list": return self._send(list_insurance_snapshots((q.get('endpoint_id') or [''])[0]))
            if p.startswith("/api/recovery/download/"):
                name=urllib.parse.unquote(p.split("/api/recovery/download/",1)[1])
                if not re.fullmatch(r"[A-Za-z0-9_.-]+\.mbxrecovery",name): return self._send({"error":"invalid recovery filename"},400)
                fp=default_home()/"recovery"/name
                if not fp.is_file(): return self._send({"error":"not found"},404)
                data=fp.read_bytes(); self.send_response(200); self.send_header("Content-Type","application/octet-stream"); self.send_header("Content-Length",str(len(data))); self.send_header("Content-Disposition",f'attachment; filename="{name}"'); self.send_header("Cache-Control","private, no-store"); self.end_headers(); self.wfile.write(data); return
            if p=="/api/sync/endpoints": return self._send(list_sync_endpoints())
            if p=="/api/sync/detect": return self._send(detect_sync_folders())
            if p=="/api/sync/devices": return self._send(list_sync_devices((q.get('endpoint_id') or [''])[0]))
            if p=="/api/sync/security": return self._send(sync_security_status((q.get('endpoint_id') or [''])[0]))
            if p=="/api/lan/status": return self._send(pairing_status())
            if p=="/api/lan/discover": return self._send(discover_peers())
            if p=="/api/memories": return self._send(list_memories(query=(q.get('query') or [''])[0] or None,category=(q.get('category') or ['all'])[0],limit=int((q.get('limit') or ['100'])[0])))
            if p.startswith("/api/memories/") and p.endswith("/related"):
                mid=p.split('/')[3]; return self._send(related_memories(mid))
            if p.startswith("/api/memories/"):
                mid=p.split('/')[3]; return self._send(get_memory(mid))
            if p.startswith("/api/attachments/"):
                sha=urllib.parse.unquote(p.split("/api/attachments/",1)[1])
                mid=(q.get('memory_id') or [None])[0]
                a=get_attachment(sha,memory_id=mid)
                fp=__import__('pathlib').Path(a['local_path'])
                if not fp.is_file(): return self._send({"error":"attachment blob missing"},404)
                data=fp.read_bytes(); self.send_response(200); self.send_header("Content-Type",a.get('mime_type') or 'application/octet-stream'); self.send_header("Content-Length",str(len(data))); self.send_header("Content-Disposition", "attachment; filename*=UTF-8''"+urllib.parse.quote(a.get('original_name') or 'attachment.bin')); self.send_header("Cache-Control","private, no-store"); self.end_headers(); self.wfile.write(data); return
            if p.startswith("/api/exports/"):
                name=urllib.parse.unquote(p.split("/api/exports/",1)[1])
                if not name or "/" in name or "\\" in name or not name.endswith(".mboxpack"):
                    return self._send({"error":"invalid export name"},400)
                fp=default_home()/"exports"/name
                if not fp.exists(): return self._send({"error":"not found"},404)
                data=fp.read_bytes(); self.send_response(200); self.send_header("Content-Type","application/octet-stream"); self.send_header("Content-Length",str(len(data))); self.send_header("Content-Disposition",f'attachment; filename="{name}"'); self.end_headers(); self.wfile.write(data); return
            if p.startswith("/api/replay/"):
                tid=urllib.parse.unquote(p.split("/api/replay/",1)[1])
                if not re.fullmatch(r"[A-Za-z0-9-]{1,80}",tid): return self._send({"error":"invalid transfer id"},400)
                fp=default_home()/"imports"/tid/"viewer.html"
                if not fp.exists(): return self._send({"error":"not found"},404)
                return self._send(fp.read_bytes(),ctype="text/html; charset=utf-8")
            return self._send({"error":"not found"},404)
        except Exception as e: return self._send({"error":str(e)},400)
    def do_POST(self):
        try:
            p=urllib.parse.urlparse(self.path).path; d=self._json()
            if p=="/api/insurance/configure": return self._send(configure_insurance(d.get('endpoint_id',''),interval_hours=int(d.get('interval_hours',24)),retention=int(d.get('retention',7)),deep_verify=bool(d.get('deep_verify',False))))
            if p=="/api/insurance/disable": return self._send(disable_insurance())
            if p=="/api/insurance/run": return self._send(run_insurance_backup(force=bool(d.get('force',True))))
            if p=="/api/insurance/verify": return self._send(verify_latest_insurance())
            if p=="/api/insurance/restore-latest": return self._send(restore_latest_insurance(d.get('endpoint_id','')))
            if p=="/api/recovery/verify":
                raw=base64.b64decode(d.get('data_base64') or '',validate=True)
                if len(raw)>4*1024*1024: raise ValueError('recovery file is unexpectedly large')
                with tempfile.NamedTemporaryFile(suffix='.mbxrecovery',delete=False) as tf: tf.write(raw); temp_path=tf.name
                try: return self._send(verify_recovery_kit(temp_path,str(d.get('recovery_code') or '')))
                finally:
                    try: __import__('os').unlink(temp_path)
                    except OSError: pass
            if p=="/api/recovery/create":
                outdir=default_home()/"recovery"; outdir.mkdir(parents=True,exist_ok=True)
                name=f"MemoryBox-Recovery-{__import__('datetime').datetime.now().strftime('%Y%m%d-%H%M%S')}.mbxrecovery"
                j=create_recovery_kit(outdir/name)
                return self._send({**j,"filename":name,"download_url":"/api/recovery/download/"+urllib.parse.quote(name)},201)
            if p=="/api/recovery/restore":
                raw=base64.b64decode(d.get('data_base64') or '',validate=True)
                if len(raw)>4*1024*1024: raise ValueError('recovery file is unexpectedly large')
                with tempfile.NamedTemporaryFile(suffix='.mbxrecovery',delete=False) as tf: tf.write(raw); temp_path=tf.name
                try: return self._send(restore_recovery_kit(temp_path,str(d.get('recovery_code') or ''),replace_existing=bool(d.get('replace_existing',False))))
                finally:
                    try: __import__('os').unlink(temp_path)
                    except OSError: pass
            if p=="/api/recovery/backup": return self._send(backup_recovery_file_to_sync(d.get('path',''),d.get('endpoint_id','')))
            if p=="/api/memories": return self._send(save_memory(d.get('content',''),title=d.get('title'),summary=d.get('summary'),category=d.get('category','auto'),tags=d.get('tags',[]),source_agent=d.get('source_agent','Memory Box UI'),source_uri=d.get('source_uri','')),201)
            if p=="/api/quick-save": return self._send(save_memory(d.get('text') or d.get('content',''),title=d.get('title'),summary=d.get('summary'),category=d.get('category','auto'),tags=d.get('tags',[]),source_agent=d.get('agent') or d.get('source_agent','Browser Bridge'),source_uri=d.get('url') or d.get('source_uri','')),201)
            if p=="/api/export-pack":
                outdir=default_home()/"exports"; outdir.mkdir(parents=True,exist_ok=True)
                name=f"MemoryBox-Transfer-{__import__('datetime').datetime.now().strftime('%Y%m%d-%H%M%S')}.mboxpack"
                r=export_transfer_bundle(outdir/name,memory_ids=d.get('memory_ids') or None,query=d.get('query') or None,category=d.get('category') or None)
                return self._send({**r,"filename":name})
            if p=="/api/import-pack":
                raw=base64.b64decode(d.get('data_base64') or '',validate=True)
                if len(raw)>64*1024*1024: raise ValueError('browser import limit is 64MB')
                name=str(d.get('filename') or 'transfer.mboxpack')
                with tempfile.NamedTemporaryFile(suffix='.mboxpack',delete=False) as tf: tf.write(raw); temp_path=tf.name
                try: return self._send(import_transfer_bundle(temp_path))
                finally:
                    try: __import__('os').unlink(temp_path)
                    except OSError: pass
            if p=="/api/resume": return self._send({"context":compose_context(d.get('memory_ids') or [])})
            if p=="/api/agents/connect": return self._send(connect_agent(d['key']))
            if p=="/api/agents/connect-all": return self._send(connect_all_detected())
            if p=="/api/sync/add": return self._send(configure_sync_folder(d.get('path',''),provider=d.get('provider','generic-folder'),name=d.get('name'),auto_import=bool(d.get('auto_import',True)),encryption_mode=d.get('encryption_mode','e2ee')),201)
            if p=="/api/sync/remove": return self._send(remove_sync_endpoint(d['endpoint_id']))
            if p=="/api/sync/trust": return self._send(trust_sync_device(d['endpoint_id'],d['device_id'],expected_fingerprint=d.get('expected_fingerprint')))
            if p=="/api/sync/untrust": return self._send(revoke_sync_device(d['endpoint_id'],d['device_id']))
            if p=="/api/sync/encryption": return self._send(set_sync_encryption(d['endpoint_id'],d['mode']))
            if p=="/api/sync/send": return self._send(publish_to_sync(d['endpoint_id'],memory_ids=d.get('memory_ids') or None,query=d.get('query'),category=d.get('category')))
            if p=="/api/sync/pull": return self._send(receive_from_sync(d['endpoint_id']))
            if p=="/api/lan/start": return self._send(start_pairing(ttl=int(d.get('ttl',300))))
            if p=="/api/lan/stop": return self._send(stop_pairing())
            if p=="/api/lan/send":
                outdir=default_home()/"exports"; outdir.mkdir(parents=True,exist_ok=True)
                temp=outdir/("LAN-"+__import__('uuid').uuid4().hex+".mboxpack")
                ex=export_transfer_bundle(temp,memory_ids=d.get('memory_ids') or None,query=d.get('query'),category=d.get('category'),include_archived=False)
                try: return self._send({"export":ex,"remote":send_pack(d['host'],int(d['port']),str(d['code']),temp)})
                finally:
                    try: temp.unlink()
                    except OSError: pass
            if p.startswith('/api/memories/') and p.endswith('/attachments'):
                mid=p.split('/')[3]; raw=base64.b64decode(d.get('data_base64') or '',validate=True)
                if len(raw)>48*1024*1024: raise ValueError('web attachment limit is 48MB; use MCP/CLI for larger local files')
                return self._send(add_attachment_bytes(mid,raw,original_name=str(d.get('filename') or 'attachment.bin'),mime_type=d.get('mime_type'),role=str(d.get('role') or 'attachment'),note=str(d.get('note') or '')),201)
            if p.startswith('/api/memories/') and p.endswith('/append'):
                return self._send(append_memory(p.split('/')[3],d.get('content','')))
            if p.startswith('/api/memories/') and p.endswith('/flag'):
                return self._send(set_flag(p.split('/')[3],d['flag'],bool(d['value'])))
            return self._send({"error":"not found"},404)
        except Exception as e: return self._send({"error":str(e)},400)


class LocalServerRuntime:
    def __init__(self, host: str, port: int):
        init_db(); auto_link_once()
        self.monitor = SyncMonitor().start()
        self.insurance_monitor = InsuranceMonitor().start()
        self.server = ThreadingHTTPServer((host, port), Handler)
        actual_host, actual_port = self.server.server_address[:2]
        self.url = f"http://{actual_host}:{actual_port}/"
        self.thread = threading.Thread(target=self.server.serve_forever, name="MemoryBoxHTTP", daemon=True)
        self._stopped = False

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        if self._stopped:
            return
        self._stopped = True
        try: self.server.shutdown()
        except Exception: pass
        try: self.server.server_close()
        except Exception: pass
        try: self.insurance_monitor.stop()
        except Exception: pass
        try: self.monitor.stop()
        except Exception: pass
        try: stop_pairing()
        except Exception: pass


def start_server(host="127.0.0.1", port=8765):
    return LocalServerRuntime(host, port).start()


def serve(host="127.0.0.1",port=8765,open_browser=True):
    runtime=start_server(host,port)
    if open_browser: threading.Timer(0.7,lambda:webbrowser.open(runtime.url)).start()
    print(f"Memory Box running at {runtime.url}")
    try:
        while runtime.thread.is_alive(): runtime.thread.join(0.5)
    except KeyboardInterrupt: pass
    finally: runtime.stop()
