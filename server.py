"""VoiceOS-facing MCP server for Something's Phishy.

Stdout belongs exclusively to the MCP transport. All diagnostics go to stderr.
"""

from __future__ import annotations

import argparse
import logging
import queue
import sys
import threading
from pathlib import Path
from typing import Any, Callable, TypeVar

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from signals import ScreenContext, analyze

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env.local")
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger("somethings-phishy")
mcp = FastMCP("somethings-phishy")

T = TypeVar("T")
CALL_TIMEOUT_SECONDS = 1.0

# Inline fallbacks unblock this track while context, explanation, and Convex
# are built in parallel. Their real modules replace these imports unchanged.
try:
    from context import capture as _capture
except (ImportError, ModuleNotFoundError):
    def _capture(surface: str = "any") -> ScreenContext:
        return ScreenContext(
            text="PayPal security check. Confirm your account now.",
            links=[("paypal.com", "https://paypa1-secure.ru/x")],
            page_url="https://paypa1-secure.ru/x",
        )

try:
    from explain import humanize as _humanize
except (ImportError, ModuleNotFoundError):
    def _humanize(value: Any, *_args: Any, **_kwargs: Any) -> Any:
        return value

try:
    from convex_client import enrich as _enrich, record_scan as _record_scan
except (ImportError, ModuleNotFoundError):
    def _enrich(result: dict[str, Any], *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return result

    def _record_scan(_result: dict[str, Any], *_args: Any, **_kwargs: Any) -> None:
        return None

_last_findings: dict[str, dict[str, Any]] = {}
_last_findings_lock = threading.Lock()


def _call_with_timeout(
    function: Callable[..., T],
    *args: Any,
    timeout: float = CALL_TIMEOUT_SECONDS,
    **kwargs: Any,
) -> T:
    """Run a possibly blocking dependency without letting it freeze VoiceOS."""
    outcome: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def invoke() -> None:
        try:
            outcome.put((True, function(*args, **kwargs)))
        except BaseException as exc:
            outcome.put((False, exc))

    threading.Thread(target=invoke, daemon=True).start()
    try:
        succeeded, value = outcome.get(timeout=timeout)
    except queue.Empty as exc:
        raise TimeoutError(f"{function.__name__} exceeded {timeout:.1f}s") from exc
    if not succeeded:
        raise value
    return value


def _safe_call(
    function: Callable[..., T],
    *args: Any,
    fallback: T,
    timeout: float = CALL_TIMEOUT_SECONDS,
    **kwargs: Any,
) -> T:
    try:
        return _call_with_timeout(function, *args, timeout=timeout, **kwargs)
    except Exception as exc:
        logger.warning("Skipping %s: %s", function.__name__, exc)
        return fallback


def _normalise_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {
            "verdict": "CAUTION",
            "findings": [],
            "finding_count": 0,
            "action": "Close this page and ask someone you trust before continuing.",
            "explainable": False,
        }
    normalised = dict(result)
    normalised["verdict"] = str(normalised.get("verdict", "CAUTION")).upper()
    findings = normalised.get("findings", [])
    normalised["findings"] = findings if isinstance(findings, list) else []
    return normalised


def render_verdict_card(result: dict[str, Any]) -> str:
    """Turn an analysis result into the complete readable and speakable card."""
    result = _normalise_result(result)
    verdict_lines = {
        "SAFE": "✅ No clear signs of a scam found.",
        "CAUTION": "⚠️ Something here needs a closer look.",
        "DANGER": "⛔ This looks dangerous.",
    }
    lines = [verdict_lines.get(result["verdict"], verdict_lines["CAUTION"])]

    for finding in result["findings"][:3]:
        if not isinstance(finding, dict):
            continue
        title = str(finding.get("title", "Warning")).strip().rstrip(".")
        evidence = str(finding.get("evidence", "")).strip()
        if evidence:
            lines.append(f"• {title}: {evidence}")

    action = str(result.get("action") or "Stop and ask someone you trust before continuing.")
    action = " ".join(action.split()).strip().rstrip(".") + "."
    lines.extend(("", f"→ {action}"))
    return "\n".join(lines)


def _remember_findings(result: dict[str, Any]) -> None:
    remembered = {
        str(finding.get("code")): dict(finding)
        for finding in result.get("findings", [])
        if isinstance(finding, dict) and finding.get("code")
    }
    with _last_findings_lock:
        _last_findings.clear()
        _last_findings.update(remembered)


def _scan(surface: str) -> str:
    context = _safe_call(_capture, surface, fallback=ScreenContext())
    result = _normalise_result(_safe_call(analyze, context, fallback=_normalise_result(None)))

    # The deterministic result remains authoritative. Enrichment can contribute
    # metadata but cannot replace its verdict, findings, or action.
    enriched = _safe_call(_enrich, dict(result), fallback=dict(result))
    if isinstance(enriched, dict):
        for key in ("enrichment", "domain_created"):
            if key in enriched:
                result[key] = enriched[key]

    humanized = _safe_call(_humanize, dict(result), fallback=dict(result))
    if isinstance(humanized, dict):
        revised_by_code = {
            str(item.get("code")): item
            for item in humanized.get("findings", [])
            if isinstance(item, dict) and item.get("code")
        }
        for finding in result["findings"]:
            if not isinstance(finding, dict):
                continue
            revised = revised_by_code.get(str(finding.get("code")))
            if revised and revised.get("title"):
                finding["title"] = str(revised["title"])
        if humanized.get("action"):
            result["action"] = str(humanized["action"])

    _remember_findings(result)
    # Never pass ScreenContext: clipboard contents and other raw capture remain
    # local. Only the deterministic, evidence-limited result may be recorded.
    _safe_call(_record_scan, dict(result), fallback=None)
    return render_verdict_card(result)


@mcp.tool()
def check_this_page() -> str:
    """Check what is on screen right now for a scam or phishing attempt.

    Use this when someone sounds worried and asks "is this safe?", "is this
    real?", "is this legitimate?", "is this a scam?", "should I click this?",
    or "something seems phishy." It checks the current webpage, email, login,
    checkout, pop-up, link, and anything asking for personal or card details.
    Also use it when the user is unsure what kind of threat they are seeing.
    """
    return _scan("page")


@mcp.tool()
def check_this_download() -> str:
    """Check a file or download before the user opens, runs, or installs it.

    Use this for "is this download safe?", "should I download/open/run this?",
    "is this installer real?", or concern about an EXE, MSI, ZIP, setup file,
    attachment, download button, browser download, or a file just downloaded.
    """
    return _scan("download")


@mcp.tool()
def check_this_transaction() -> str:
    """Check a crypto payment, wallet request, or address before approval.

    Use this when someone asks "is this transaction safe?", "should I approve
    this?", "is this wallet prompt real?", or mentions crypto, Bitcoin,
    Ethereum, a token swap, wallet connection, payment address, or copied
    wallet address. Check before they send money or sign anything.
    """
    return _scan("transaction")


@mcp.tool()
def check_my_clipboard() -> str:
    """Check for a dangerous command secretly copied by a website.

    Route here when a page told the user to press Windows+R or Win+R, open Run,
    PowerShell, Command Prompt, Terminal, or paste a command to prove they are
    human, fix an error, install an update, or complete a CAPTCHA. Also use for
    "what did this site copy?" or "is what I copied safe?" Never repeat or send
    the raw clipboard contents anywhere; only report locally detected danger.
    """
    return _scan("clipboard")



@mcp.tool()
def why_is_that_bad(finding_code: str) -> str:
    """Explain one warning from the most recent check in calm, plain language.

    Use when the user asks "why is that bad?", "what does that warning mean?",
    "why is that dangerous?", or wants more detail about a flagged item. Pass
    the finding code from the previous scan. Do not use this to make a new
    safety verdict; it only explains evidence already found by the local check.
    """
    with _last_findings_lock:
        finding = _last_findings.get(finding_code)
    if finding is None:
        return "I cannot find that warning. Run the safety check again, then ask about the warning it shows."

    fallback = (
        f"{finding.get('title', 'This was flagged')}. "
        f"The check observed: {finding.get('evidence', 'suspicious content')}. "
        "Do not continue until you have verified it another way."
    )
    explanation = _safe_call(_humanize, dict(finding), fallback=fallback)
    return explanation if isinstance(explanation, str) else fallback


@mcp.tool()
def alert_my_guardian() -> str:
    """Notify the user's trusted contact about the current suspicious screen.

    Use only when the user asks "alert my guardian", "tell my trusted contact",
    "get someone I trust", "send this to my daughter/son/caregiver", or asks
    for help from their safety contact. This records a fresh local check for
    the guardian without sharing raw clipboard text. It does not call police,
    a bank, emergency services, or anyone who is not the configured contact.
    """
    context = _safe_call(_capture, "any", fallback=ScreenContext())
    result = _normalise_result(
        _safe_call(analyze, context, fallback=_normalise_result(None))
    )
    payload = dict(result)
    payload["alert_guardian"] = True
    recorded = _safe_call(_record_scan, payload, fallback=False)
    if recorded is False:
        return "I could not reach your trusted contact. Stop here and contact someone you trust directly."
    return "Your trusted contact has been alerted. Stop here and wait for them to help you."


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Something's Phishy MCP server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="serve streamable HTTP on http://127.0.0.1:8765/mcp",
    )
    args = parser.parse_args(argv)
    if args.http:
        mcp.settings.host = "127.0.0.1"
        mcp.settings.port = 8765
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
