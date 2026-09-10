from __future__ import annotations

import json
import os
import platform
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterable

from .db import default_home, init_db
from .insurance import run_insurance_backup
from .sync import sync_all
from .transfer import import_transfer_bundle
from .crypto import decrypt_file_for_local_device
from .insurance import restore_insurance_snapshot
from .webapp import start_server

APP_NAME = "Memory Box"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "MemoryBox"

DEFAULT_DESKTOP_SETTINGS: dict[str, Any] = {
    "minimize_to_tray": True,
    "start_on_login": False,
    "notifications": True,
    "close_behavior": "tray",
}


def desktop_settings_path(home: Path | None = None) -> Path:
    base = Path(home or default_home())
    return base / "desktop.json"


def load_desktop_settings(home: Path | None = None) -> dict[str, Any]:
    p = desktop_settings_path(home)
    data: dict[str, Any] = {}
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw
        except Exception:
            data = {}
    out = dict(DEFAULT_DESKTOP_SETTINGS)
    out.update({k: data[k] for k in DEFAULT_DESKTOP_SETTINGS if k in data})
    return out


def save_desktop_settings(settings: dict[str, Any], home: Path | None = None) -> dict[str, Any]:
    p = desktop_settings_path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    merged = dict(DEFAULT_DESKTOP_SETTINGS)
    merged.update({k: settings[k] for k in DEFAULT_DESKTOP_SETTINGS if k in settings})
    p.write_text(json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return merged


def is_windows() -> bool:
    return platform.system().lower() == "windows"


def _startup_command(executable: str | None = None) -> str:
    exe = executable or sys.executable
    exe_path = str(Path(exe).resolve())
    frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return f'"{exe_path}" --minimized'
    main = Path(__file__).resolve().parents[1] / "memorybox_desktop.py"
    if not main.exists():
        main = Path(__file__).resolve().parents[1] / "memorybox_main.py"
        return f'"{exe_path}" "{main}" desktop --minimized'
    return f'"{exe_path}" "{main}" --minimized'


def set_start_on_login(enabled: bool, *, executable: str | None = None, home: Path | None = None) -> dict[str, Any]:
    if not is_windows():
        return {"supported": False, "enabled": False, "reason": "Windows only"}
    import winreg
    command = _startup_command(executable)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass
    settings = load_desktop_settings(home)
    settings["start_on_login"] = bool(enabled)
    save_desktop_settings(settings, home)
    return {"supported": True, "enabled": bool(enabled), "command": command if enabled else None}


def get_start_on_login(*, home: Path | None = None) -> bool:
    if not is_windows():
        return bool(load_desktop_settings(home).get("start_on_login", False))
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, RUN_VALUE)
            return True
    except Exception:
        return False


def process_open_path(path: str | os.PathLike[str], *, db_path=None) -> dict[str, Any]:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(p)
    suffix = p.suffix.lower()
    if suffix == ".mboxpack" or (p.is_dir() and (p / "manifest.json").exists()):
        result = import_transfer_bundle(p, db_path=db_path)
        return {"kind": "transfer", "path": str(p), "result": result}
    if suffix == ".mboxenc":
        import tempfile
        with tempfile.TemporaryDirectory(prefix="memorybox-desktop-decrypt-") as td:
            dec = Path(td) / "decrypted.payload"
            decrypt_file_for_local_device(p, dec, db_path=db_path)
            try:
                result = import_transfer_bundle(dec, db_path=db_path)
                kind = "encrypted-transfer"
            except Exception:
                result = restore_insurance_snapshot(p, db_path=db_path)
                kind = "insurance"
        return {"kind": kind, "path": str(p), "result": result}
    if suffix == ".mbxrecovery":
        return {
            "kind": "recovery",
            "path": str(p),
            "requires_user_secret": True,
            "message": "Open the Recovery page and enter the recovery code locally.",
        }
    raise ValueError(f"unsupported Memory Box file: {p.name}")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _make_tray_icon_image():
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((10, 10, 118, 118), radius=30, fill=(29, 29, 31, 255))
    draw.rounded_rectangle((31, 31, 97, 97), radius=18, outline=(255, 255, 255, 235), width=7)
    draw.line((48, 63, 63, 78, 83, 49), fill=(255, 255, 255, 245), width=7, joint="curve")
    return image


class DesktopBridge:
    def __init__(self, home: Path | None = None):
        self.home = Path(home or default_home())
        self.window = None
        self.tray = None
        self.runtime = None
        self.quitting = False
        self._first_hide_notice = False

    def attach(self, *, window=None, tray=None, runtime=None):
        if window is not None:
            self.window = window
        if tray is not None:
            self.tray = tray
        if runtime is not None:
            self.runtime = runtime

    def notify(self, message: str, title: str = APP_NAME) -> None:
        if not load_desktop_settings(self.home).get("notifications", True):
            return
        try:
            if self.tray is not None and getattr(self.tray, "HAS_NOTIFICATION", False):
                self.tray.notify(message, title)
        except Exception:
            pass

    def show(self):
        if self.window is not None:
            try:
                self.window.show()
                self.window.restore()
            except Exception:
                pass
        return {"ok": True}

    def hide(self):
        if self.window is not None:
            try:
                self.window.hide()
            except Exception:
                pass
        if not self._first_hide_notice:
            self.notify("Memory Box is still running in the system tray.")
            self._first_hide_notice = True
        return {"ok": True}

    def quit(self):
        self.quitting = True
        try:
            if self.tray is not None:
                self.tray.stop()
        except Exception:
            pass
        try:
            if self.runtime is not None:
                self.runtime.stop()
        except Exception:
            pass
        try:
            if self.window is not None:
                self.window.destroy()
        except Exception:
            pass
        return {"ok": True}

    def get_desktop_status(self):
        settings = load_desktop_settings(self.home)
        settings["start_on_login"] = get_start_on_login(home=self.home)
        return {
            "desktop": True,
            "platform": platform.system(),
            "settings": settings,
            "home": str(self.home),
        }

    def set_minimize_to_tray(self, enabled: bool):
        settings = load_desktop_settings(self.home)
        settings["minimize_to_tray"] = bool(enabled)
        settings["close_behavior"] = "tray" if enabled else "quit"
        return save_desktop_settings(settings, self.home)

    def set_notifications(self, enabled: bool):
        settings = load_desktop_settings(self.home)
        settings["notifications"] = bool(enabled)
        return save_desktop_settings(settings, self.home)

    def set_start_on_login(self, enabled: bool):
        return set_start_on_login(bool(enabled), home=self.home)

    def import_path(self, path: str):
        result = process_open_path(path)
        if result["kind"] == "recovery":
            self.show()
            self._run_js("view('recovery');toastMsg('已打开恢复页面；恢复码只在本机输入。')")
        else:
            self.show()
            self._run_js("view('memories');loadMemoriesData('');toastMsg('导入完成')")
            self.notify(f"Imported {Path(path).name}")
        return result

    def sync_now(self):
        result = sync_all()
        self.notify("Device sync check completed.")
        self._run_js("home()")
        return result

    def insure_now(self):
        result = run_insurance_backup(force=True)
        self.notify("Insurance snapshot completed." if result.get("ok") else "Insurance snapshot needs attention.")
        self._run_js("home()")
        return result

    def _run_js(self, code: str):
        try:
            if self.window is not None:
                self.window.run_js(code)
        except Exception:
            pass


def _bind_drag_drop(window, bridge: DesktopBridge):
    try:
        from webview.dom import DOMEventHandler

        def on_drag(_event):
            return None

        def on_drop(event):
            files = (event or {}).get("dataTransfer", {}).get("files", [])
            imported = 0
            rejected = 0
            for file_info in files:
                path = file_info.get("pywebviewFullPath")
                if not path:
                    continue
                try:
                    bridge.import_path(path)
                    imported += 1
                except Exception:
                    rejected += 1
            if imported:
                bridge._run_js(f"toastMsg('已导入 {imported} 个 Memory Box 文件')")
            elif rejected:
                bridge._run_js("toastMsg('拖入的文件无法导入')")

        doc = window.dom.document
        doc.events.dragenter += DOMEventHandler(on_drag, prevent_default=True, stop_propagation=True)
        doc.events.dragover += DOMEventHandler(on_drag, prevent_default=True, stop_propagation=True, debounce=300)
        doc.events.drop += DOMEventHandler(on_drop, prevent_default=True, stop_propagation=True)
    except Exception:
        # Drag/drop is a desktop enhancement; file associations and the import page remain available.
        pass


def run_desktop(paths: Iterable[str] | None = None, *, minimized: bool = False, home: Path | None = None) -> int:
    init_db()
    try:
        import webview
        import pystray
        from pystray import Menu, MenuItem
    except Exception as exc:
        # Keep a useful fallback for source/bootstrap installs where optional desktop deps are absent.
        from .webapp import serve
        print(f"Desktop shell unavailable ({exc}); opening local web UI instead.")
        serve(open_browser=True)
        return 0

    bridge = DesktopBridge(home)
    port = _free_port()
    runtime = start_server(host="127.0.0.1", port=port)
    bridge.attach(runtime=runtime)
    url = runtime.url

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True

    window = webview.create_window(
        APP_NAME,
        url=url,
        js_api=bridge,
        width=1280,
        height=820,
        min_size=(900, 620),
        resizable=True,
        hidden=bool(minimized),
        background_color="#f5f5f7",
        text_select=True,
        shadow=True,
    )
    bridge.attach(window=window)

    def tray_open(icon=None, item=None):
        bridge.show()

    def tray_sync(icon=None, item=None):
        try:
            bridge.sync_now()
        except Exception as e:
            bridge.notify(f"Sync failed: {e}")

    def tray_insure(icon=None, item=None):
        try:
            bridge.insure_now()
        except Exception as e:
            bridge.notify(f"Insurance failed: {e}")

    def tray_quit(icon=None, item=None):
        bridge.quit()

    tray = pystray.Icon(
        "memorybox",
        _make_tray_icon_image(),
        APP_NAME,
        menu=Menu(
            MenuItem("Open Memory Box", tray_open, default=True),
            MenuItem("Sync now", tray_sync),
            MenuItem("Run insurance", tray_insure),
            Menu.SEPARATOR,
            MenuItem("Quit", tray_quit),
        ),
    )
    bridge.attach(tray=tray)

    def on_closing(*_args):
        if bridge.quitting:
            return True
        settings = load_desktop_settings(bridge.home)
        if settings.get("minimize_to_tray", True) and bridge.tray is not None:
            bridge.hide()
            return False
        bridge.quitting = True
        try:
            runtime.stop()
        except Exception:
            pass
        try:
            tray.stop()
        except Exception:
            pass
        return True

    def on_minimized(*_args):
        if load_desktop_settings(bridge.home).get("minimize_to_tray", True):
            time.sleep(0.08)
            bridge.hide()

    window.events.closing += on_closing
    window.events.minimized += on_minimized

    initial_paths = [str(Path(p).expanduser()) for p in (paths or [])]

    def desktop_start(win):
        _bind_drag_drop(win, bridge)
        for p in initial_paths:
            try:
                result = bridge.import_path(p)
                if result.get("kind") == "recovery":
                    continue
            except Exception as e:
                bridge.notify(f"Could not open {Path(p).name}: {e}")
        if minimized:
            bridge.notify("Memory Box started in the system tray.")

    try:
        tray.run_detached()
        webview.start(desktop_start, window, gui="edgechromium", debug=False)
    finally:
        bridge.quitting = True
        try:
            tray.stop()
        except Exception:
            pass
        try:
            runtime.stop()
        except Exception:
            pass
    return 0


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(prog="memorybox-desktop")
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--minimized", action="store_true")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    return run_desktop(args.paths, minimized=args.minimized)
