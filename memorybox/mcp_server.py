from __future__ import annotations

import json
import sys
from typing import Any

from . import __version__
from .db import append_memory, bundle_by_query, category_counts, compose_context, get_memory, list_memories, merge_memories, related_memories, save_memory, set_flag
from .attachments import add_attachment, list_attachments, remove_attachment
from .transfer import export_transfer_bundle, import_transfer_bundle, inspect_transfer_bundle
from .sync import configure_sync_folder, detect_sync_folders, list_sync_devices, list_sync_endpoints, publish_to_sync, receive_from_sync, sync_now, trust_sync_device, revoke_sync_device, sync_security_status, set_sync_encryption
from .lan import discover_peers, pairing_status, send_pack, start_pairing, stop_pairing
from .crypto import public_identity
from .insurance import insurance_settings, run_insurance_backup, disaster_readiness, verify_latest_insurance

TOOLS = [
    {"name":"memory_save","description":"Save the relevant part of the current conversation into the local Memory Box. Use when the user says save/remember this conversation.","inputSchema":{"type":"object","properties":{"content":{"type":"string"},"title":{"type":"string"},"summary":{"type":"string"},"category":{"type":"string"},"tags":{"type":"array","items":{"type":"string"}},"source_agent":{"type":"string"},"source_uri":{"type":"string"}},"required":["content"]}},
    {"name":"memory_list","description":"List recent saved memories, optionally filtered by category or query.","inputSchema":{"type":"object","properties":{"query":{"type":"string"},"category":{"type":"string"},"limit":{"type":"integer","minimum":1,"maximum":200}}}},
    {"name":"memory_get","description":"Open one saved memory by stable id such as M000007.","inputSchema":{"type":"object","properties":{"memory_id":{"type":"string"}},"required":["memory_id"]}},
    {"name":"memory_append","description":"Append new conversation context to an existing memory while keeping a version snapshot.","inputSchema":{"type":"object","properties":{"memory_id":{"type":"string"},"content":{"type":"string"}},"required":["memory_id","content"]}},
    {"name":"memory_categories","description":"Show memory categories and counts.","inputSchema":{"type":"object","properties":{}}},
    {"name":"memory_resume","description":"Build a continuation context from one or more saved memory ids so the agent can continue previous work.","inputSchema":{"type":"object","properties":{"memory_ids":{"type":"array","items":{"type":"string"}}},"required":["memory_ids"]}},
    {"name":"memory_related","description":"Find memories related to a saved memory within the local vault.","inputSchema":{"type":"object","properties":{"memory_id":{"type":"string"},"limit":{"type":"integer","minimum":1,"maximum":50}},"required":["memory_id"]}},
    {"name":"memory_bundle","description":"Retrieve all relevant memories for a topic/project and compose one resume context.","inputSchema":{"type":"object","properties":{"query":{"type":"string"},"category":{"type":"string"},"limit":{"type":"integer","minimum":1,"maximum":50}},"required":["query"]}},
    {"name":"memory_merge","description":"Merge two or more saved memories into a new consolidated memory. Source memories are preserved unless archive_sources is true.","inputSchema":{"type":"object","properties":{"memory_ids":{"type":"array","items":{"type":"string"},"minItems":2},"title":{"type":"string"},"archive_sources":{"type":"boolean"}},"required":["memory_ids"]}},
    {"name":"memory_pin","description":"Pin or unpin a memory.","inputSchema":{"type":"object","properties":{"memory_id":{"type":"string"},"value":{"type":"boolean"}},"required":["memory_id","value"]}},
    {"name":"memory_favorite","description":"Favorite or unfavorite a memory.","inputSchema":{"type":"object","properties":{"memory_id":{"type":"string"},"value":{"type":"boolean"}},"required":["memory_id","value"]}},
    {"name":"memory_export_pack","description":"Export one or more memories and all linked attachment files into a portable .mboxpack complete-session capsule for another computer running Memory Box.","inputSchema":{"type":"object","properties":{"output":{"type":"string"},"memory_ids":{"type":"array","items":{"type":"string"}},"query":{"type":"string"},"category":{"type":"string"}},"required":["output"]}},
    {"name":"memory_import_pack","description":"Import a portable Memory Box .mboxpack or transfer folder. Conflicting remote ids are safely remapped rather than overwritten.","inputSchema":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}},
    {"name":"memory_inspect_pack","description":"Inspect a Memory Box transfer package before importing it.","inputSchema":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}},
    {"name":"memory_attach_file","description":"Attach a local file (PDF, Word, image, code, CSV, log, etc.) to a saved memory. The file is copied into Memory Box and content-addressed by SHA-256. Use only when the agent can access the local path.","inputSchema":{"type":"object","properties":{"memory_id":{"type":"string"},"path":{"type":"string"},"role":{"type":"string"},"note":{"type":"string"}},"required":["memory_id","path"]}},
    {"name":"memory_list_attachments","description":"List files attached to a saved memory, including local restored paths and SHA-256 hashes.","inputSchema":{"type":"object","properties":{"memory_id":{"type":"string"}},"required":["memory_id"]}},
    {"name":"memory_detach_file","description":"Remove a file link from a memory. The shared content-addressed blob is preserved by default.","inputSchema":{"type":"object","properties":{"memory_id":{"type":"string"},"sha256":{"type":"string"},"delete_orphan_blob":{"type":"boolean"}},"required":["memory_id","sha256"]}},
    {"name":"memory_device_identity","description":"Show this Memory Box device's E2EE public identity and verification fingerprint. The private key is never returned.","inputSchema":{"type":"object","properties":{}}},
    {"name":"memory_sync_trust_device","description":"Trust a visible Memory Box device for end-to-end encrypted sync after the user verifies its fingerprint on both devices.","inputSchema":{"type":"object","properties":{"endpoint_id":{"type":"string"},"device_id":{"type":"string"},"expected_fingerprint":{"type":"string"}},"required":["endpoint_id","device_id"]}},
    {"name":"memory_sync_untrust_device","description":"Revoke a previously trusted sync device so future encrypted packages are no longer addressed to it.","inputSchema":{"type":"object","properties":{"endpoint_id":{"type":"string"},"device_id":{"type":"string"}},"required":["endpoint_id","device_id"]}},
    {"name":"memory_sync_security","description":"Show E2EE mode, local device fingerprint, and trusted recipient devices for a sync endpoint.","inputSchema":{"type":"object","properties":{"endpoint_id":{"type":"string"}},"required":["endpoint_id"]}},
    {"name":"memory_sync_set_encryption","description":"Set a sync endpoint to e2ee or legacy-plaintext. New endpoints default to e2ee; use plaintext only for explicit legacy compatibility.","inputSchema":{"type":"object","properties":{"endpoint_id":{"type":"string"},"mode":{"type":"string","enum":["e2ee","legacy-plaintext"]}},"required":["endpoint_id","mode"]}},
    {"name":"memory_sync_add_folder","description":"Configure a shared sync folder. New endpoints default to E2EE. Use provider baidu-netdisk for a Baidu Netdisk-synchronized local folder; credentials are never requested.","inputSchema":{"type":"object","properties":{"path":{"type":"string"},"provider":{"type":"string"},"name":{"type":"string"},"auto_import":{"type":"boolean"},"encryption_mode":{"type":"string","enum":["e2ee","legacy-plaintext"]}},"required":["path"]}},
    {"name":"memory_sync_endpoints","description":"List configured cross-device sync folders, including Baidu Netdisk, OneDrive, NAS and generic folders.","inputSchema":{"type":"object","properties":{}}},
    {"name":"memory_sync_detect","description":"Best-effort detect local cloud/sync folders. Detection never configures or modifies a folder automatically.","inputSchema":{"type":"object","properties":{}}},
    {"name":"memory_sync_send","description":"Publish selected memories and attachments as a verified .mboxpack into a configured shared sync folder for another Memory Box device.","inputSchema":{"type":"object","properties":{"endpoint_id":{"type":"string"},"memory_ids":{"type":"array","items":{"type":"string"}},"query":{"type":"string"},"category":{"type":"string"}},"required":["endpoint_id"]}},
    {"name":"memory_sync_pull","description":"Import new verified Memory Box packages found in a configured sync folder. Duplicate packages are ignored.","inputSchema":{"type":"object","properties":{"endpoint_id":{"type":"string"}},"required":["endpoint_id"]}},
    {"name":"memory_sync_devices","description":"List Memory Box device presence records visible through a configured sync folder.","inputSchema":{"type":"object","properties":{"endpoint_id":{"type":"string"}},"required":["endpoint_id"]}},
    {"name":"memory_insurance_status","description":"Show automatic encrypted insurance-backup configuration and the last run. This never exposes recovery codes or private keys.","inputSchema":{"type":"object","properties":{}}},
    {"name":"memory_insurance_health","description":"Run a disaster-readiness health check for the local Memory Box. Reports database, attachment, recovery-file and encrypted-backup readiness without asking for the recovery code.","inputSchema":{"type":"object","properties":{"deep":{"type":"boolean"}}}},
    {"name":"memory_insurance_run","description":"Run the configured full encrypted insurance snapshot now. The snapshot contains the complete memory library and managed attachments and is encrypted before entering the configured cloud/sync folder.","inputSchema":{"type":"object","properties":{"force":{"type":"boolean"}}}},
    {"name":"memory_insurance_verify_latest","description":"Decrypt and structurally verify the latest automatic insurance snapshot using the local device identity, without importing it.","inputSchema":{"type":"object","properties":{}}},
    {"name":"memory_lan_pair","description":"Open a short-lived LAN receiving window and return a one-time pairing code. v0.9 encrypts payloads end-to-end and also authenticates the transfer with the pairing code.","inputSchema":{"type":"object","properties":{"ttl":{"type":"integer","minimum":30,"maximum":900}}}},
    {"name":"memory_lan_discover","description":"Discover Memory Box devices that currently have a LAN pairing window open.","inputSchema":{"type":"object","properties":{}}},
    {"name":"memory_lan_send_pack","description":"Send an existing .mboxpack to a paired Memory Box device on a trusted private LAN.","inputSchema":{"type":"object","properties":{"host":{"type":"string"},"port":{"type":"integer"},"code":{"type":"string"},"path":{"type":"string"}},"required":["host","port","code","path"]}},
]


def _text(obj: Any) -> dict[str,Any]:
    s = obj if isinstance(obj,str) else json.dumps(obj,ensure_ascii=False,indent=2)
    return {"content":[{"type":"text","text":s}]}


def call_tool(name: str, a: dict[str,Any]) -> dict[str,Any]:
    if name=="memory_save": return _text(save_memory(a["content"],title=a.get("title"),summary=a.get("summary"),category=a.get("category","auto"),tags=a.get("tags",[]),source_agent=a.get("source_agent","mcp-agent"),source_uri=a.get("source_uri","")))
    if name=="memory_list": return _text(list_memories(query=a.get("query"),category=a.get("category"),limit=min(int(a.get("limit",50)),200)))
    if name=="memory_get": return _text(get_memory(a["memory_id"]))
    if name=="memory_append": return _text(append_memory(a["memory_id"],a["content"]))
    if name=="memory_categories": return _text(category_counts())
    if name=="memory_resume": return _text(compose_context(a["memory_ids"]))
    if name=="memory_related": return _text(related_memories(a["memory_id"],int(a.get("limit",8))))
    if name=="memory_bundle": return _text(bundle_by_query(a["query"],category=a.get("category"),limit=int(a.get("limit",10))))
    if name=="memory_merge": return _text(merge_memories(a["memory_ids"],title=a.get("title"),archive_sources=bool(a.get("archive_sources",False))))
    if name=="memory_pin": return _text(set_flag(a["memory_id"],"pinned",bool(a["value"])))
    if name=="memory_favorite": return _text(set_flag(a["memory_id"],"favorite",bool(a["value"])))
    if name=="memory_export_pack": return _text(export_transfer_bundle(a["output"],memory_ids=a.get("memory_ids"),query=a.get("query"),category=a.get("category")))
    if name=="memory_import_pack": return _text(import_transfer_bundle(a["path"]))
    if name=="memory_inspect_pack": return _text(inspect_transfer_bundle(a["path"]))
    if name=="memory_attach_file": return _text(add_attachment(a["memory_id"],a["path"],role=a.get("role","attachment"),note=a.get("note","")))
    if name=="memory_list_attachments": return _text(list_attachments(a["memory_id"]))
    if name=="memory_detach_file": return _text(remove_attachment(a["memory_id"],a["sha256"],delete_orphan_blob=bool(a.get("delete_orphan_blob",False))))
    if name=="memory_device_identity": return _text(public_identity())
    if name=="memory_insurance_status": return _text(insurance_settings())
    if name=="memory_insurance_health": return _text(disaster_readiness(deep=bool(a.get("deep",False))))
    if name=="memory_insurance_run": return _text(run_insurance_backup(force=bool(a.get("force",True))))
    if name=="memory_insurance_verify_latest": return _text(verify_latest_insurance())
    if name=="memory_sync_trust_device": return _text(trust_sync_device(a["endpoint_id"],a["device_id"],expected_fingerprint=a.get("expected_fingerprint")))
    if name=="memory_sync_untrust_device": return _text(revoke_sync_device(a["endpoint_id"],a["device_id"]))
    if name=="memory_sync_security": return _text(sync_security_status(a["endpoint_id"]))
    if name=="memory_sync_set_encryption": return _text(set_sync_encryption(a["endpoint_id"],a["mode"]))
    if name=="memory_sync_add_folder": return _text(configure_sync_folder(a["path"],provider=a.get("provider","generic-folder"),name=a.get("name"),auto_import=bool(a.get("auto_import",True)),encryption_mode=a.get("encryption_mode","e2ee")))
    if name=="memory_sync_endpoints": return _text(list_sync_endpoints())
    if name=="memory_sync_detect": return _text(detect_sync_folders())
    if name=="memory_sync_send": return _text(publish_to_sync(a["endpoint_id"],memory_ids=a.get("memory_ids"),query=a.get("query"),category=a.get("category")))
    if name=="memory_sync_pull": return _text(receive_from_sync(a["endpoint_id"]))
    if name=="memory_sync_devices": return _text(list_sync_devices(a["endpoint_id"]))
    if name=="memory_lan_pair": return _text(start_pairing(ttl=int(a.get("ttl",300))))
    if name=="memory_lan_discover": return _text(discover_peers())
    if name=="memory_lan_send_pack": return _text(send_pack(a["host"],int(a["port"]),a["code"],a["path"]))
    raise KeyError(name)


def _write(msg: dict[str,Any]) -> None:
    sys.stdout.write(json.dumps(msg,ensure_ascii=False,separators=(",",":")) + "\n")
    sys.stdout.flush()


def run_stdio() -> int:
    for raw in sys.stdin:
        raw=raw.strip()
        if not raw: continue
        try:
            req=json.loads(raw); rid=req.get("id"); method=req.get("method","")
            if method=="initialize":
                pv=(req.get("params") or {}).get("protocolVersion") or "2025-06-18"
                result={"protocolVersion":pv,"capabilities":{"tools":{"listChanged":False}},"serverInfo":{"name":"Memory Box","version":__version__}}
            elif method=="tools/list": result={"tools":TOOLS}
            elif method=="tools/call":
                p=req.get("params") or {}; result=call_tool(p.get("name",""),p.get("arguments") or {})
            elif method in {"notifications/initialized","ping"}:
                if rid is None: continue
                result={}
            else:
                if rid is None: continue
                _write({"jsonrpc":"2.0","id":rid,"error":{"code":-32601,"message":"Method not found"}}); continue
            if rid is not None: _write({"jsonrpc":"2.0","id":rid,"result":result})
        except Exception as exc:
            try:
                if 'rid' in locals() and rid is not None: _write({"jsonrpc":"2.0","id":rid,"error":{"code":-32000,"message":str(exc)}})
            except Exception: pass
    return 0
