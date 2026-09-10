from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AGENTS = {
    "kimi-code": {"name":"Kimi Code / Kimi CLI","mode":"MCP stdio"},
    "workbuddy": {"name":"WorkBuddy","mode":"MCP + Skill connector"},
    "cursor": {"name":"Cursor","mode":"MCP stdio"},
    "gemini-cli": {"name":"Gemini CLI","mode":"MCP stdio"},
    "claude-code": {"name":"Claude Code","mode":"MCP stdio"},
    "codex": {"name":"OpenAI Codex CLI","mode":"MCP stdio"},
    "chatgpt": {"name":"ChatGPT","mode":"Remote MCP / plugin bridge"},
    "windsurf": {"name":"Windsurf","mode":"MCP (manual adapter)"},
    "codebuddy": {"name":"Tencent CodeBuddy","mode":"MCP stdio"},
    "qoder": {"name":"Qoder / Qoder CN","mode":"MCP stdio"},
    "trae": {"name":"TRAE / TraeWork","mode":"MCP (client/cloud dependent)"},
    "generic": {"name":"Generic Agent","mode":"MCP stdio / REST / Skill"},
}


def _home() -> Path:
    return Path.home()


def server_command() -> tuple[str,list[str]]:
    # Works from source, embedded Python, or PyInstaller-style executable.
    if getattr(sys, "frozen", False):
        return sys.executable, ["mcp"]
    script = Path(__file__).resolve().parents[1] / "memorybox_main.py"
    exe = Path(sys.executable)
    # The GUI may be launched with pythonw.exe, but MCP stdio requires a console
    # interpreter with working stdin/stdout pipes. Prefer the sibling python.exe.
    if exe.name.lower() in {"pythonw.exe", "pythonw"}:
        sibling = exe.with_name("python.exe" if exe.suffix.lower() == ".exe" else "python")
        if sibling.exists():
            exe = sibling
    return str(exe), [str(script), "mcp"]


def _json_merge_server(path: Path, server: dict[str,Any], key: str = "mcpServers") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if path.exists():
        raw = path.read_text(encoding="utf-8")
        try:
            parsed = json.loads(raw)
        except Exception as exc:
            raise ValueError(f"Refusing to overwrite malformed JSON config: {path}: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"Refusing to overwrite non-object JSON config: {path}")
        data = parsed
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = path.with_name(path.name + f".memorybox.bak.{stamp}")
        shutil.copy2(path, backup)
    block = data.setdefault(key,{})
    if not isinstance(block,dict): block={}; data[key]=block
    block["memory-box"] = server
    tmp = path.with_suffix(path.suffix+".memorybox.tmp")
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)


def scan_agents() -> list[dict[str,Any]]:
    h = _home()
    checks = {
        "kimi-code": bool(shutil.which("kimi") or (h/".kimi").exists() or (h/".kimi-code").exists()),
        "workbuddy": any(p.exists() for p in [h/".workbuddy", Path(os.environ.get("APPDATA",""))/"WorkBuddy"] if str(p)),
        "cursor": bool(shutil.which("cursor-agent") or (h/".cursor").exists()),
        "gemini-cli": bool(shutil.which("gemini") or (h/".gemini").exists()),
        "claude-code": bool(shutil.which("claude") or (h/".claude").exists()),
        "codex": bool(shutil.which("codex") or (h/".codex").exists()),
        "chatgpt": False,  # localhost MCP is not directly attachable; use browser/remote bridge.
        "windsurf": bool((h/".codeium"/"windsurf").exists() or shutil.which("windsurf")),
        "codebuddy": bool(shutil.which("codebuddy")),
        "qoder": bool(shutil.which("qoder") or shutil.which("qodercn")),
        "trae": bool(shutil.which("trae") or (Path(os.environ.get("APPDATA",""))/"Trae").exists()),
        "generic": True,
    }
    return [{"key":k,"name":AGENTS[k]["name"],"mode":AGENTS[k]["mode"],"detected":bool(checks.get(k))} for k in AGENTS]


def connect_agent(key: str) -> dict[str,Any]:
    if key not in AGENTS: raise ValueError(f"unknown agent: {key}")
    cmd,args = server_command()
    server = {"command":cmd,"args":args}
    h = _home()
    if key == "cursor":
        path = h/".cursor"/"mcp.json"; _json_merge_server(path,server); return {"connected":True,"path":str(path),"mode":"config"}
    if key == "gemini-cli":
        path = h/".gemini"/"settings.json"; _json_merge_server(path,server); return {"connected":True,"path":str(path),"mode":"config"}
    if key == "kimi-code":
        # Kimi Code's documented user-level path is ~/.kimi-code/mcp.json.
        # If a legacy ~/.kimi/mcp.json already exists, update it too for compatibility.
        targets=[h/".kimi-code"/"mcp.json"]
        legacy=h/".kimi"/"mcp.json"
        if legacy.exists(): targets.append(legacy)
        for p in targets: _json_merge_server(p,server)
        return {"connected":True,"path":"; ".join(map(str,targets)),"mode":"config"}
    if key == "claude-code":
        exe = shutil.which("claude")
        if not exe: return {"connected":False,"manual":True,"reason":"Claude Code CLI not detected","command":f'claude mcp add --transport stdio --scope user memory-box -- "{cmd}" ' + " ".join(f'"{a}"' for a in args)}
        cp = subprocess.run([exe,"mcp","add","--transport","stdio","--scope","user","memory-box","--",cmd,*args],capture_output=True,text=True,timeout=20)
        return {"connected":cp.returncode==0,"mode":"cli","stdout":cp.stdout[-1000:],"stderr":cp.stderr[-1000:]}
    if key == "codex":
        exe = shutil.which("codex")
        manual = f'codex mcp add memory-box -- "{cmd}" ' + " ".join(f'"{a}"' for a in args)
        if not exe: return {"connected":False,"manual":True,"reason":"Codex CLI not detected","command":manual}
        # Codex CLI supports mcp add in current releases; use help-driven command and fail safely.
        cp = subprocess.run([exe,"mcp","add","memory-box","--",cmd,*args],capture_output=True,text=True,timeout=20)
        return {"connected":cp.returncode==0,"mode":"cli","stdout":cp.stdout[-1000:],"stderr":cp.stderr[-1000:],"manual_command":manual}
    if key == "workbuddy":
        return {"connected":False,"manual":True,"reason":"Use the bundled WorkBuddy connector package; WorkBuddy controls connector installation.","connector":"integrations/workbuddy"}
    if key == "codebuddy":
        exe = shutil.which("codebuddy")
        manual = f'codebuddy mcp add --scope user memory-box -- "{cmd}" ' + " ".join(f'"{a}"' for a in args)
        if not exe: return {"connected":False,"manual":True,"reason":"CodeBuddy CLI not detected","command":manual}
        cp = subprocess.run([exe,"mcp","add","--scope","user","memory-box","--",cmd,*args],capture_output=True,text=True,timeout=20)
        return {"connected":cp.returncode==0,"mode":"cli","stdout":cp.stdout[-1000:],"stderr":cp.stderr[-1000:],"manual_command":manual}
    if key == "qoder":
        exe = shutil.which("qodercn") or shutil.which("qoder")
        binary = Path(exe).name if exe else "qoder"
        manual = f'{binary} mcp add -s user memory-box -- "{cmd}" ' + " ".join(f'"{a}"' for a in args)
        if not exe: return {"connected":False,"manual":True,"reason":"Qoder CLI not detected","command":manual}
        cp = subprocess.run([exe,"mcp","add","-s","user","memory-box","--",cmd,*args],capture_output=True,text=True,timeout=20)
        return {"connected":cp.returncode==0,"mode":"cli","stdout":cp.stdout[-1000:],"stderr":cp.stderr[-1000:],"manual_command":manual}
    if key == "trae":
        return {"connected":False,"manual":True,"reason":"TRAE/TraeWork MCP configuration depends on the client or enterprise cloud environment. Add this stdio server where local MCP is supported, or expose Memory Box through an approved remote bridge.","server":server}
    if key == "chatgpt":
        return {"connected":False,"manual":True,"reason":"ChatGPT cannot directly reach a localhost MCP server. Use a supported Secure MCP Tunnel / custom app, or the Skill export workflow.","mode":"remote-mcp-required"}
    if key in {"windsurf","generic"}:
        return {"connected":False,"manual":True,"server":server,"reason":"Use this stdio MCP definition in the agent's MCP settings."}
    raise ValueError(key)

def connect_all_detected() -> list[dict[str,Any]]:
    results=[]
    for a in scan_agents():
        if not a['detected'] or a['key'] in {'generic','chatgpt'}:
            continue
        try:
            r=connect_agent(a['key'])
            results.append({'key':a['key'],'name':a['name'],**r})
        except Exception as exc:
            results.append({'key':a['key'],'name':a['name'],'connected':False,'error':str(exc)})
    return results


def _state_dir() -> Path:
    if os.environ.get("MEMORYBOX_HOME"):
        return Path(os.environ["MEMORYBOX_HOME"]).expanduser().resolve()
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "MemoryBox"
    return Path.home() / ".memorybox"

def auto_link_once() -> dict[str,Any]:
    """Auto-register detected local MCP clients exactly once.

    Set MEMORYBOX_NO_AUTOLINK=1 to disable. Unsupported/cloud clients are
    reported but not modified.
    """
    state=_state_dir(); state.mkdir(parents=True,exist_ok=True); marker=state/'autolink.json'
    if os.environ.get('MEMORYBOX_NO_AUTOLINK') == '1':
        return {'skipped':True,'reason':'MEMORYBOX_NO_AUTOLINK=1'}
    from . import __version__
    if marker.exists():
        try:
            previous=json.loads(marker.read_text(encoding='utf-8'))
            if previous.get('version') == __version__:
                return previous
        except Exception:
            pass
    result={'completed':True,'version':__version__,'results':connect_all_detected()}
    marker.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result
