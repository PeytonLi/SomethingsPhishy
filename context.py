"""Windows context capture with a three-rung degradation ladder."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from io import BytesIO
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import urlopen

try:
    import pyperclip
except ImportError:
    pyperclip = None  # type: ignore[assignment]

try:
    import websocket
except ImportError:
    websocket = None  # type: ignore[assignment]

# Prime pyperclip's Win32 backend outside the capture hot path.
if pyperclip is not None:
    try:
        pyperclip.paste()
    except Exception:
        pass

from signals import ScreenContext

CDP_URL = "http://127.0.0.1:9222"
CDP_TIMEOUT = 0.8
DOWNLOAD_FRESHNESS_SECONDS = 15 * 60
DOM_EXPRESSION = r"""(() => {
  const bodyText = document.body ? document.body.innerText : '';
  const sender = document.querySelector('[email][name], [data-hovercard-id]');
  const replyTo = document.querySelector('[data-reply-to], [data-tooltip*="Reply-To" i]');
  return JSON.stringify({
    text: bodyText.slice(0, 20000),
    links: [...document.querySelectorAll('a')].slice(0, 300)
          .map(a => [a.innerText.trim().slice(0,120), a.href]),
    iframes: [...document.querySelectorAll('iframe')]
          .map(f => { try { return new URL(f.src).origin } catch(e) { return '' } }),
    hasPasswordField: !!document.querySelector('input[type=password]'),
    hasCardField: /card number|cvv|cvc/i.test(bodyText),
    fromDisplay: sender ? (sender.getAttribute('name') || sender.textContent || '').trim() : '',
    fromAddress: sender ? (sender.getAttribute('email') || sender.getAttribute('data-hovercard-id') || '').trim() : '',
    replyTo: replyTo ? (replyTo.getAttribute('data-reply-to') || replyTo.textContent || '').trim() : ''
  });
})()"""


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
    if pyperclip is None:
        return ""
    try:
        value = pyperclip.paste()
        return value if isinstance(value, str) else str(value)
    except Exception:
        return ""


def _recent_downloads(
    limit: int = 5,
    max_age_seconds: float = DOWNLOAD_FRESHNESS_SECONDS,
) -> list[dict[str, Any]]:
    """Return only recently modified files, newest first."""
    root = Path(os.environ.get("USERPROFILE", Path.home())) / "Downloads"
    cutoff_ns = time.time_ns() - int(max_age_seconds * 1_000_000_000)
    candidates: list[tuple[Path, os.stat_result]] = []
    try:
        paths = list(root.iterdir())
    except (OSError, ValueError):
        return []
    for path in paths:
        try:
            if not path.is_file():
                continue
            stat = path.stat()
        except OSError:
            continue
        if stat.st_mtime_ns >= cutoff_ns:
            candidates.append((path, stat))

    candidates.sort(key=lambda item: item[1].st_mtime_ns, reverse=True)
    return [
        {
            "path": path,
            "filename": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "zone": zone_identifier(path),
        }
        for path, stat in candidates[:limit]
    ]


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
    """Select a CDP page only when its title clearly matches the foreground."""
    foreground = " ".join(_foreground_title().split()).casefold()
    if not foreground:
        raise LookupError("foreground window has no title")
    for target in targets:
        title = " ".join(str(target.get("title", "")).split()).casefold()
        if not title:
            continue
        if foreground == title:
            return target
        separators = (" - ", " — ", " | ")
        if any(foreground.startswith(title + separator) for separator in separators):
            return target
        if any(title.startswith(foreground + separator) for separator in separators):
            return target
    raise LookupError("no CDP target confidently matches the foreground window")


def _cdp_dom(target: dict[str, Any]) -> dict[str, Any]:
    if websocket is None:
        raise RuntimeError("websocket-client is unavailable")
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


def _foreground_bounds() -> tuple[int, int, int, int] | None:
    """Return the foreground window rectangle for an in-memory screenshot."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        rect = wintypes.RECT()
        if not hwnd or not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        if rect.right <= rect.left or rect.bottom <= rect.top:
            return None
        return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        return None


def capture_screenshot() -> bytes | None:
    """Return an in-memory image of the foreground window, or None on failure."""
    try:
        from PIL import Image, ImageGrab

        bounds = _foreground_bounds()
        if bounds is None:
            return None

        image = ImageGrab.grab(bbox=bounds)
        width, height = image.size
        if width > 1440:
            resized_height = max(1, round(height * 1440 / width))
            image = image.resize(
                (1440, resized_height),
                Image.Resampling.LANCZOS,
            )

        output = BytesIO()
        image.save(output, format="WEBP", quality=80, method=4)
        return output.getvalue()
    except Exception:
        return None


def _ocr_context() -> tuple[str | None, str]:
    """OCR the foreground window entirely in memory when providers are present."""
    try:
        from PIL import ImageGrab
        import winocr

        bounds = _foreground_bounds()
        image = ImageGrab.grab(bbox=bounds) if bounds else ImageGrab.grab()
        result = winocr.recognize_pil_sync(image)
        if isinstance(result, dict):
            text = result.get("text", "")
        else:
            text = result
        return None, text if isinstance(text, str) else str(text or "")
    except Exception:
        return None, ""


_ADDRESS_PATTERNS = (
    re.compile(r"(?<![0-9A-Fa-f])0x[0-9A-Fa-f]{40}(?![0-9A-Fa-f])"),
    re.compile(r"(?<![A-Za-z0-9])[13][a-km-zA-HJ-NP-Z1-9]{25,34}(?![A-Za-z0-9])"),
    re.compile(r"(?<![A-Za-z0-9])bc1[ac-hj-np-z02-9]{11,71}(?![A-Za-z0-9])", re.I),
)
_PAYMENT_CONTEXT = re.compile(
    r"\b(?:send|pay|payment|recipient|wallet|deposit|withdraw|transfer|address)\b",
    re.I,
)
_TRANSACTION_IDENTIFIER = re.compile(r"(?:transaction\s*(?:id|hash)|txid)\s*[:#-]?\s*$", re.I)


def _address_candidates(value: str) -> list[re.Match[str]]:
    return sorted(
        (match for pattern in _ADDRESS_PATTERNS for match in pattern.finditer(value)),
        key=lambda match: match.start(),
    )


def _displayed_crypto_address(text: str) -> str | None:
    for match in _address_candidates(text):
        prefix = text[max(0, match.start() - 100):match.start()]
        if _TRANSACTION_IDENTIFIER.search(prefix[-40:]):
            continue
        if _PAYMENT_CONTEXT.search(prefix):
            return match.group(0)
    return None


def _clipboard_crypto_address(text: str) -> str | None:
    stripped = text.strip()
    matches = _address_candidates(stripped)
    if len(matches) == 1 and matches[0].span() == (0, len(stripped)):
        return matches[0].group(0)
    return None


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def capture(surface: str = "any") -> ScreenContext:
    """Capture current Windows context; never raise when a rung is unavailable."""
    surface_key = surface.casefold()
    include_downloads = surface_key in {"any", "download"}
    downloads = _recent_downloads() if include_downloads else []
    newest = downloads[0] if downloads else {}
    zone = newest.get("zone", {})
    clipboard_text = _clipboard_text()
    observed_fields: set[str] = {"clipboard_text"}
    context = CapturedContext(
        clipboard_text=clipboard_text,
        download_filename=newest.get("filename"),
        file_size_bytes=newest.get("size_bytes"),
        download_url=zone.get("HostUrl"),
        download_host_url=zone.get("HostUrl"),
        download_referrer_url=zone.get("ReferrerUrl"),
        zone_id=zone.get("ZoneId"),
        recent_downloads=downloads,
        observed_fields=observed_fields,
    )
    if include_downloads:
        observed_fields.add("downloads")

    # UIA is the foreground-grounded baseline. CDP may enrich it, but may not
    # replace it with content from an unrelated background browser tab.
    page_url, text = _uia_context()
    if page_url or text:
        context.page_url = page_url
        context.text = text
        context.capture_rung = 2
        context.capture_source = "uia+clipboard" + ("+downloads" if include_downloads else "")
        if page_url:
            observed_fields.add("page_url")
        if text:
            observed_fields.add("text")

    try:
        target = _pick_target(_cdp_targets())
        dom = _cdp_dom(target)
        context.page_url = _optional_text(target.get("url")) or context.page_url
        dom_text = str(dom.get("text", "") or "")
        if dom_text:
            context.text = dom_text
        context.links = [
            (str(link[0]), str(link[1]))
            for link in dom.get("links", [])
            if isinstance(link, (list, tuple)) and len(link) == 2
        ]
        context.iframe_origins = [str(origin) for origin in dom.get("iframes", []) if origin]
        context.from_display = _optional_text(dom.get("fromDisplay"))
        context.from_address = _optional_text(dom.get("fromAddress"))
        context.reply_to = _optional_text(dom.get("replyTo"))
        observed_fields.update({
            "page_url", "text", "links", "iframe_origins",
            "from_display", "from_address", "reply_to",
        })
        context.capture_rung = 1
        context.capture_source = "uia+cdp+clipboard" + ("+downloads" if include_downloads else "")
    except Exception:
        pass

    if not context.text:
        ocr_url, ocr_text = _ocr_context()
        if ocr_url or ocr_text:
            context.page_url = context.page_url or ocr_url
            context.text = ocr_text
            context.capture_rung = min(context.capture_rung, 2)
            context.capture_source += "+ocr"
            observed_fields.add("text")

    if surface_key in {"transaction", "crypto"}:
        context.displayed_address = _displayed_crypto_address(context.text)
        context.clipboard_address = _clipboard_crypto_address(context.clipboard_text)
        observed_fields.update({"displayed_address", "clipboard_address"})

    return context
