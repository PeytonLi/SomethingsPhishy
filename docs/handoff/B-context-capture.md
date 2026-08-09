# Track B — Windows context capture

**Branch:** `track/context` · **Owns:** `context.py`, `scripts/` · **Read first:** [`docs/PRD.md`](../PRD.md) §6.3 (all of it) and [`README.md`](README.md)

## Mission

Turn "whatever is on this Windows machine right now" into a `ScreenContext`. This is the track PRD v1.0 got wrong — it was written for macOS. Every primitive here is different.

## Hour 0, before writing any code

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="$env:LOCALAPPDATA\SomethingsPhishy\chrome-profile"

curl.exe http://127.0.0.1:9222/json/version
```

If that second command fails, **stop and solve it before anything else.** Chrome ≥136 refuses the debug port on the default user-data-dir, which is why the second flag is mandatory and why this is the single most likely way to lose the demo. It fails silently at the worst possible moment. PRD §6.3.1.

## Build, in this order

Build **rung 3 first**. It has zero external dependencies, cannot break on stage, and on its own already demos ClickFix — the best beat in the script.

**Rung 3 — no browser needed:**
1. `pyperclip.paste()` → `clipboard_text`. In-process Win32, ~1 ms. **Never** shell out to `Get-Clipboard` (300–600 ms).
2. `%USERPROFILE%\Downloads`, top 5 by mtime → filename, ext, size.
3. Zone.Identifier ADS per file → `HostUrl`, `ReferrerUrl`, `ZoneId`. PRD §6.3.2 has the function. `open(f"{path}:Zone.Identifier")` — a plain file read, no `xattr`, no plist, no base64. This is genuinely better than the macOS original: one read replaces two.

**Rung 1 — full fidelity:**
4. `GET http://127.0.0.1:9222/json` → filter `type == "page"`, drop `chrome://` and `devtools://`. Gives `page_url` with no websocket.
5. Websocket to the target's `webSocketDebuggerUrl`, `Runtime.evaluate` with `returnByValue: true`, JS payload verbatim from PRD §6.3.1 → `text`, `links`, `iframe_origins`.

**Rung 2 — degraded:**
6. UIA reads the foreground window's address bar for a URL, plus window text. Lose href mismatch and iframe origins; keep everything else.

Also ship `scripts/start-chrome.ps1` so demo-day setup is one command.

## Contract

You produce, never define:
```python
from signals import ScreenContext
def capture(surface: str = "any") -> ScreenContext: ...
```
Track C is adding `clipboard_text`, `download_host_url`, `download_referrer_url` to `ScreenContext`. Until they land, set them via a local subclass or coordinate with C — do not edit `signals.py`.

## Gotchas

- **Hard-timeout the websocket at 800 ms** and degrade. Never hang; a frozen tool call is worse than a degraded verdict.
- **CDP does not reliably tell you which tab is focused.** Cross-check the foreground window title from UIA against target titles; fall back to the first page target.
- **The debug profile is a separate Chrome.** No bookmarks, no logged-in sessions. Fine for demo (arguably better — no personal data on the projector), but demo tabs must be opened in *that* window.
- **Files on FAT32/exFAT have no ADS.** Missing Zone.Identifier there means "unknown", not "suspicious". Only treat absence as the `MOTW_STRIPPED` signal on NTFS volumes.
- Edge works identically (`msedge.exe`, same flags) and is preinstalled — a reasonable backup if Chrome misbehaves.
- Never `print()`. `server.py` imports you.

## Done when

- [ ] `capture()` returns a populated `ScreenContext` at all three ladder rungs
- [ ] Each rung degrades without raising, and reports which rung it achieved
- [ ] Clipboard read < 10 ms; full rung-1 capture < 400 ms
- [ ] Zone.Identifier parsed from a real browser download (verify `HostUrl` matches where you got it)
- [ ] `scripts/start-chrome.ps1` works from a cold boot on the demo machine
- [ ] Zero subprocess spawns in the capture path

## Suggested skills

`superpowers:systematic-debugging` — CDP failures are opaque and you will hit at least one; resist guess-and-check. `superpowers:test-driven-development` for the Zone.Identifier parser and the ladder-degradation logic: both are pure functions over fixture strings, and the degradation paths are exactly what you can't test manually on stage.
