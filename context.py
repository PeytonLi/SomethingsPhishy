"""Windows context capture with a three-rung degradation ladder."""
from __future__ import annotations

import ctypes
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import urlopen
import websocket
import pyperclip
# Prime pyperclip’s Win32 backend outside the capture hot path.
try:
    pyperclip.paste()
except Exception:
    pass

from signals import ScreenContext

CDP_URL = "http://127.0.0.1:9222"
CDP_TIMEOUT = 0.8
DOM_EXPRESSION = r"""JSON.stringify({
  text: document.body ? document.body.innerText.slice(0, 20000) : '',
  links: [...document.querySelectorAll('a')].slice(0, 300)
        .map(a => [a.innerText.trim().slice(0,120), a.href]),
  iframes: [...document.querySelectorAll('iframe')]
        .map(f => { try { return new URL(f.src).origin } catch(e) { return '' } }),
  hasPasswordField: !!document.querySelector('input[type=password]'),
  hasCardField: /card number|cvv|cvc/i.test(document.body ? document.body.innerText : '')
})"""


@dataclass
class CapturedContext(ScreenContext):
    """ScreenContext plus temporary Windows fields pending Track C's additions."""

    clipboard_text: str = ""
    download_host_url: str | None = None
    download_referrer_url: str | None = None
    capture_rung: int = 3
    capture_source: str = "clipboard+downloads"
    zone_id: str | None = None
    recent_downloads: list[dict[str, Any]] = field(default_factory=list)


def zone_identifier(path: Path) -> dict[str, str]:
    """Read a Mark of the Web Zone.Transfer ADS; absence means unknown."""
    try:
        raw = Path(f"{path}:Zone.Identifier").read_text(errors="replace")
    except OSError:
        return {}
    return dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)


def _clipboard_text() -> str:
    try:

        value = pyperclip.paste()
        return value if isinstance(value, str) else str(value)
    except Exception:
        return ""


def _recent_downloads(limit: int = 5) -> list[dict[str, Any]]:
    root = Path(os.environ.get("USERPROFILE", Path.home())) / "Downloads"
    try:
        files = sorted(
            (path for path in root.iterdir() if path.is_file()),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )[:limit]
    except (OSError, ValueError):
        return []

    result = []
    for path in files:
        try:
            stat = path.stat()
        except OSError:
            continue
        result.append({
            "path": path,
            "filename": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "zone": zone_identifier(path),
        })
    return result


def _foreground_title() -> str:
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value
    except Exception:
        return ""


def _cdp_targets() -> list[dict[str, Any]]:
    with urlopen(f"{CDP_URL}/json", timeout=CDP_TIMEOUT) as response:
        targets = json.loads(response.read().decode("utf-8"))
    return [
        target for target in targets
        if target.get("type") == "page"
        and not str(target.get("url", "")).startswith(("chrome://", "devtools://"))
    ]


def _pick_target(targets: list[dict[str, Any]]) -> dict[str, Any]:
    if not targets:
        raise LookupError("no capturable page target")
    foreground = _foreground_title().casefold()
    for target in targets:
        title = str(target.get("title", "")).strip().casefold()
        if title and (title in foreground or foreground in title):
            return target
    return targets[0]


def _cdp_dom(target: dict[str, Any]) -> dict[str, Any]:
    ws = websocket.create_connection(
        target["webSocketDebuggerUrl"], timeout=CDP_TIMEOUT, suppress_origin=True
    )
    try:
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": DOM_EXPRESSION, "returnByValue": True},
        }))
        deadline = time.monotonic() + CDP_TIMEOUT
        while time.monotonic() < deadline:
            response = json.loads(ws.recv())
            if response.get("id") == 1:
                result = response.get("result", {}).get("result", {})
                if result.get("subtype") == "error":
                    raise RuntimeError(result.get("description", "CDP evaluation failed"))
                return json.loads(result.get("value", "{}"))
        raise TimeoutError("CDP Runtime.evaluate timed out")
    finally:
        ws.close()


def _uia_context() -> tuple[str | None, str]:
    try:
        import uiautomation as auto

        root = auto.GetForegroundControl()
        chunks: list[str] = []
        page_url = None
        for control in root.GetDescendants(maxDepth=8):
            name = str(getattr(control, "Name", "") or "").strip()
            if name:
                chunks.append(name)
            if page_url is None and getattr(control, "ControlTypeName", "") == "EditControl":
                try:
                    value = str(control.GetValuePattern().Value or "").strip()
                except Exception:
                    value = ""
                if value.startswith(("http://", "https://")):
                    page_url = value
        return page_url, "\n".join(dict.fromkeys(chunks))[:20000]
    except Exception:
        return None, ""


def capture(surface: str = "any") -> ScreenContext:
    """Capture current Windows context; never raise when a rung is unavailable."""
    del surface
    downloads = _recent_downloads()
    newest = downloads[0] if downloads else {}
    zone = newest.get("zone", {})
    context = CapturedContext(
        clipboard_text=_clipboard_text(),
        download_filename=newest.get("filename"),
        file_size_bytes=newest.get("size_bytes"),
        download_url=zone.get("HostUrl"),
        download_host_url=zone.get("HostUrl"),
        download_referrer_url=zone.get("ReferrerUrl"),
        zone_id=zone.get("ZoneId"),
        recent_downloads=downloads,
    )
    try:
        target = _pick_target(_cdp_targets())
        dom = _cdp_dom(target)
        context.page_url = target.get("url")
        context.text = str(dom.get("text", ""))
        context.links = [
            tuple(link) for link in dom.get("links", [])
            if isinstance(link, list) and len(link) == 2
        ]
        context.iframe_origins = [str(origin) for origin in dom.get("iframes", []) if origin]
        context.capture_rung = 1
        context.capture_source = "cdp+clipboard+downloads"
        return context
    except Exception:
        pass

    page_url, text = _uia_context()
    if page_url or text:
        context.page_url = page_url
        context.text = text
        context.capture_rung = 2
        context.capture_source = "uia+clipboard+downloads"
    return context
