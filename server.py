"""VoiceOS-facing MCP server for Something's Phishy.

Stdout belongs exclusively to the MCP transport. All diagnostics go to stderr.
"""

from __future__ import annotations

import argparse
import logging
import queue
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from signals import ScreenContext, analyze, registrable
from signals import _host as _url_host  # same project; no public url->host helper

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env.local")
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger("somethings-phishy")
mcp = FastMCP("somethings-phishy")

T = TypeVar("T")
CALL_TIMEOUT_SECONDS = 1.0
ENRICHMENT_TIMEOUT_SECONDS = 0.35
ENRICHMENT_WRAPPER_TIMEOUT_SECONDS = 0.45
RECORD_TIMEOUT_SECONDS = 0.05
_VERBATIM_CARD_INSTRUCTION = (
    "<!-- VoiceOS: Relay the safety card below verbatim. Preserve its verdict, "
    "line breaks, bold labels, and every bullet. Do not summarize, paraphrase, "
    "or add claims. -->\n"
)

# Optional providers must degrade without fabricating evidence.
try:
    from context import capture as _capture, capture_screenshot as _capture_screenshot
except (ImportError, ModuleNotFoundError):
    def _capture(surface: str = "any") -> ScreenContext:
        del surface
        return ScreenContext(observed_fields=set())

    def _capture_screenshot() -> bytes | None:
        return None

try:
    from explain import humanize as _humanize
except (ImportError, ModuleNotFoundError):
    def _humanize(value: Any, *_args: Any, **_kwargs: Any) -> Any:
        return value

try:
    from convex_client import enrich as _enrich, record_scan as _record_scan
except (ImportError, ModuleNotFoundError):
    # Signatures mirror convex_client exactly — a stub that drifts from the real
    # module fails silently once the import starts succeeding.
    def _enrich(domain: str, timeout: float = 1.5) -> dict[str, Any]:
        return {}

    def _record_scan(
        verdict: str,
        codes: list[str],
        domain: str | None = None,
        **_kwargs: Any,
    ) -> None:
        return None

try:
    from a1mobile import CallResult, place_guardian_call as _place_guardian_call
except (ImportError, ModuleNotFoundError):
    class CallResult:
        def __init__(self, placed: bool, message: str) -> None:
            self.placed = placed
            self.message = message

    def _place_guardian_call(timeout: float = 5) -> CallResult:
        del timeout
        return CallResult(False, "Guardian calling is not configured.")

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
        name = getattr(function, "__name__", type(function).__name__)
        raise TimeoutError(f"{name} exceeded {timeout:.2f}s") from exc
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
        name = getattr(function, "__name__", type(function).__name__)
        logger.warning("Skipping %s: %s", name, exc)
        return fallback


def _voice_card(card: str) -> str:
    """Mark a rendered card as final while keeping the instruction invisible."""
    return _VERBATIM_CARD_INSTRUCTION + card


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


def _safe_observations(context: ScreenContext, surface: str) -> list[str]:
    """Describe positive evidence actually observed for a clean local verdict."""
    observations: list[str] = []
    page_host = _url_host(context.page_url or "")
    if page_host:
        transport = "HTTPS" if (context.page_url or "").lower().startswith("https://") else "HTTP"
        observations.append(
            f"Website address: You are on “{page_host}”. "
            + ("The connection is encrypted." if transport == "HTTPS" else "The connection is not encrypted.")
        )

    stripe_hosts = [
        _url_host(origin if "://" in origin else f"https://{origin}")
        for origin in context.iframe_origins
    ]
    stripe_host = next(
        (host for host in stripe_hosts if registrable(host) == "stripe.com"),
        None,
    )
    if stripe_host:
        observations.append(
            f"Payment form: The card form comes from Stripe at “{stripe_host}”."
        )

    text = (context.text or "").casefold()
    method_labels = [
        label for phrase, label in (
            ("apple pay", "Apple Pay"),
            ("paypal", "PayPal"),
            ("amazon pay", "Amazon Pay"),
            ("google pay", "Google Pay"),
            ("coinbase commerce", "Coinbase Commerce"),
        )
        if phrase in text
    ]
    if method_labels:
        methods = ", ".join(method_labels)
        observations.append(
            f"Payment choices: {methods} are ways to pay. They are not the store or product name."
        )

    if len(observations) < 3 and context.links and (
        context.observed_fields is None or "links" in context.observed_fields
    ):
        count = len(context.links)
        how_many = "the one link" if count == 1 else f"all {count} links"
        observations.append(
            f"Links: I checked {how_many} on this page. "
            f"None of them said one website and opened another."
        )

    if len(observations) < 3 and surface in {"transaction", "crypto"}:
        if context.displayed_address and context.clipboard_address:
            observations.append(
                "Wallet address: The address on screen matches the address on the clipboard."
            )

    # Downloads. capture() populates these for the "download" and "any"
    # surfaces, but nothing here used to read them — so asking about a file in
    # Downloads fell straight through to the filler below and read as generic.
    filename = getattr(context, "download_filename", None)
    if filename:
        size = None
        for record in getattr(context, "recent_downloads", []) or []:
            if record.get("filename") == filename:
                size = record.get("size_bytes")
                break
        size_note = f" It is {size / 1_048_576:.1f} MB." if isinstance(size, int) and size else ""
        observations.append(f"File I checked: “{filename}”.{size_note}")

        source = getattr(context, "download_host_url", None)
        referrer = getattr(context, "download_referrer_url", None)
        source_host = _url_host(source or "")
        referrer_host = _url_host(referrer or "")
        if source_host and referrer_host and registrable(source_host) != registrable(referrer_host):
            observations.append(
                f"Where it came from: The page was “{referrer_host}” but the file "
                f"itself downloaded from “{source_host}”."
            )
        elif source_host:
            observations.append(f"Where it came from: It downloaded from “{source_host}”.")
        elif getattr(context, "zone_id", None) is None:
            observations.append(
                "Where it came from: Windows kept no record of where this file was "
                "downloaded from, so I could not confirm its source."
            )

    # Native windows (Notepad, Mail, a wallet app). Without a page_url every
    # branch above skips, which made non-browser checks look broken even when
    # the text was captured fine.
    if not page_host and (context.text or "").strip():
        observations.append(
            f"What I read: I read {len(context.text.split())} words from the "
            f"window open in front of you, not a web page."
        )

    if not observations:
        observations.append(
            "What I checked: I read what is on screen right now and found nothing "
            "matching a known scam pattern."
        )
    # Deliberately no padding to three. Filler bullets are what made every
    # answer read the same; two real observations beat three with one invented.
    return observations[:3]


def render_verdict_card(result: dict[str, Any]) -> str:
    """Turn an analysis result into the complete readable and speakable card."""
    result = _normalise_result(result)
    # "This page looks okay" is wrong when the thing checked was a file in
    # Downloads or a Notepad window. Name what was actually examined.
    subject = {
        "download": "file",
        "transaction": "transaction",
        "crypto": "transaction",
        "window": "window",   # a native app, e.g. Notepad — there is no page
    }.get(str(result.get("surface", "")), "page")
    verdict_lines = {
        "SAFE": f"This {subject} looks okay.",
        "CAUTION": f"Please pause. I could not fully confirm this {subject} is safe.",
        "DANGER": "This looks dangerous. Do not continue.",
    }
    blocks = [verdict_lines.get(result["verdict"], verdict_lines["CAUTION"])]

    if result["verdict"] == "SAFE":
        for observation in result.get("observations", [])[:3]:
            if not isinstance(observation, str) or not observation.strip():
                continue
            label, separator, detail = observation.strip().partition(":")
            if separator:
                blocks.append(f"• **{label.strip()}**\n  {detail.strip()}")
            else:
                blocks.append(f"• **Why**\n  {observation.strip()}")
    else:
        for finding in result["findings"][:3]:
            if not isinstance(finding, dict):
                continue
            title = str(finding.get("title", "Warning")).strip().rstrip(".")
            evidence = str(finding.get("evidence", "")).strip()
            if evidence:
                blocks.append(f"• **{title}**\n  {evidence}")

    # PRD §6.9: exactly one action, always. This had been dropped, so DANGER
    # cards ended on evidence and never said what to do about it. Rendered as a
    # labelled block rather than "→ ..." because the card is read aloud, and an
    # arrow glyph is noise in speech.
    action = str(result.get("action", "")).strip()
    if action and result["verdict"] != "SAFE":
        blocks.append(f"• **What to do**\n  {action}")

    return "\n\n".join(blocks)


def _remember_findings(result: dict[str, Any]) -> None:
    remembered = {
        str(finding.get("code")): dict(finding)
        for finding in result.get("findings", [])
        if isinstance(finding, dict) and finding.get("code")
    }
    with _last_findings_lock:
        _last_findings.clear()
        _last_findings.update(remembered)


def _domain_created(enrichment: dict[str, Any]) -> datetime | None:
    """RDAP registration date out of Convex intel, as an aware datetime."""
    intel = enrichment.get("intel")
    if not isinstance(intel, dict):
        return None
    registered_at = intel.get("registeredAt")
    if not isinstance(registered_at, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(registered_at / 1000, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def _scan(surface: str) -> str:
    context = _safe_call(
        _capture, surface, fallback=ScreenContext(observed_fields=set())
    )
    has_evidence = bool(
        context.text or context.links or context.page_url or context.clipboard_text
        or context.download_filename or context.from_address
        or context.displayed_address or context.clipboard_address
    )
    if not has_evidence:
        return render_verdict_card({
            "verdict": "CAUTION",
            "findings": [{
                "code": "CAPTURE_UNAVAILABLE",
                "title": "I couldn't inspect the active window",
                "evidence": "No readable page, app text, clipboard, or recent download was available.",
            }],
            "finding_count": 1,
            "action": "Keep this window open and try the check again before continuing.",
            "explainable": False,
        })

    # Enrichment has to run BEFORE analyze(): domain age is a DECISIVE finding,
    # so it must reach the engine while the verdict is still being computed.
    # Convex stays optional — on timeout this degrades to the local verdict.
    domain = registrable(_url_host(context.page_url or ""))
    enrichment = _safe_call(
        _enrich,
        domain,
        ENRICHMENT_TIMEOUT_SECONDS,
        fallback={},
        timeout=ENRICHMENT_WRAPPER_TIMEOUT_SECONDS,
    ) if domain else {}
    if not isinstance(enrichment, dict):
        enrichment = {}

    try:
        result = _normalise_result(analyze(context, _domain_created(enrichment)))
    except Exception as exc:
        logger.warning("Local analysis failed: %s", exc)
        result = _normalise_result(None)
    if enrichment:
        result["enrichment"] = enrichment
    # The card names what was examined ("this file" vs "this page"), so the
    # surface has to survive as far as the renderer. A page check that found no
    # URL was really a native window (Notepad, Mail), not a page.
    if surface == "page" and not context.page_url and (context.text or "").strip():
        result["surface"] = "window"
    else:
        result["surface"] = surface
    if result.get("verdict") == "SAFE":
        result["observations"] = _safe_observations(context, surface)

    # Keep model calls off the initial verdict's latency-critical path.
    # deterministic titles/actions are already user-facing; optional DeepSeek
    # explanation belongs in the explicit why_is_that_bad follow-up.

    _remember_findings(result)
    # Never pass ScreenContext: clipboard contents and other raw capture stay
    # local. Only verdict, finding codes, the registrable domain, and a hash of
    # page text leave the machine — convex_client does the hashing.
    # Routine SAFE checks are useful to the person asking, but they are not
    # alerts and should not clutter the guardian's shared history.
    if result.get("verdict") != "SAFE":
        _safe_call(
            _record_scan,
            str(result.get("verdict", "")),
            [
                str(finding.get("code"))
                for finding in result["findings"]
                if isinstance(finding, dict) and finding.get("code")
            ],
            domain or None,
            fallback=None,
            timeout=RECORD_TIMEOUT_SECONDS,
            surface=surface,
            findings=result["findings"],
            text=context.text or None,
        )
    return render_verdict_card(result)


@mcp.tool()
def check_this_page() -> str:
    """Check what is on screen right now for a scam or phishing attempt.

    Use this when someone sounds worried and asks "is this safe?", "is this
    real?", "is this legitimate?", "is this a scam?", "should I click this?",
    or "something seems phishy." It checks the current webpage, email, login,
    checkout, pop-up, link, and anything asking for personal or card details.
    Also use it when the user is unsure what kind of threat they are seeing.

    OUTPUT CONTRACT: the returned safety card is the complete final answer.
    Relay it verbatim, preserving the verdict line, line breaks, bold labels,
    and every bullet. Do not summarize or paraphrase it. Never replace it
    with "No, this is not a scam," and never add unsupported claims such as
    "official," "encrypted checkout," or a named subscription/product.

    Treat this tool as the only authority for the verdict. If the tool times out,
    errors, or cannot inspect the screen, say that verification failed and tell
    the user not to continue yet. Never infer or announce SAFE from the visible
    brand, URL, page appearance, or your own knowledge after a tool failure.
    """
    return _voice_card(_scan("page"))


@mcp.tool()
def check_this_download() -> str:
    """Check a file or download before the user opens, runs, or installs it.

    Use this for "is this download safe?", "should I download/open/run this?",
    "is this installer real?", or concern about an EXE, MSI, ZIP, setup file,
    attachment, download button, browser download, or a file just downloaded.
    Relay the returned card verbatim, preserving bold labels and every bullet;
    do not summarize, paraphrase, or add claims.
    """
    return _voice_card(_scan("download"))


@mcp.tool()
def check_this_transaction() -> str:
    """Check a crypto payment, wallet request, or address before approval.

    Use this when someone asks "is this transaction safe?", "should I approve
    this?", "is this wallet prompt real?", or mentions crypto, Bitcoin,
    Ethereum, a token swap, wallet connection, payment address, or copied
    wallet address. Check before they send money or sign anything.
    Relay the returned card verbatim, preserving bold labels and every bullet;
    do not summarize, paraphrase, or add claims.
    """
    return _voice_card(_scan("transaction"))


@mcp.tool()
def check_my_clipboard() -> str:
    """Check for a dangerous command secretly copied by a website.

    Route here when a page told the user to press Windows+R or Win+R, open Run,
    PowerShell, Command Prompt, Terminal, or paste a command to prove they are
    human, fix an error, install an update, or complete a CAPTCHA. Also use for
    "what did this site copy?" or "is what I copied safe?" Never repeat or send
    the raw clipboard contents anywhere; only report locally detected danger.
    Relay the returned card verbatim, preserving bold labels and every bullet;
    do not summarize, paraphrase, or add claims.
    """
    return _voice_card(_scan("clipboard"))



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
    screenshot = _safe_call(_capture_screenshot, fallback=None)
    result = _normalise_result(
        _safe_call(analyze, context, fallback=_normalise_result(None))
    )
    _safe_call(
        _record_scan,
        str(result.get("verdict", "")),
        [
            str(finding.get("code"))
            for finding in result["findings"]
            if isinstance(finding, dict) and finding.get("code")
        ],
        registrable(_url_host(context.page_url or "")) or None,
        fallback=None,
        surface="guardian",
        findings=result["findings"],
        text=context.text or None,
        screenshot=screenshot,
    )
    call_result = _safe_call(
        _place_guardian_call,
        fallback=CallResult(False, "Guardian calling is not configured."),
        timeout=6.0,
    )
    if call_result.placed:
        return (
            "I've shared the alert and called Peyton. Stop here and wait for "
            "them, and if you don't hear back, call someone you trust directly."
        )
    return (
        "I've shared the alert in Peyton's dashboard, but I couldn't place the "
        f"phone call. {call_result.message}"
    )


def main(argv: list[str] | None = None) -> None:
    # Verdict cards lead with ⛔/⚠️/✅ and Windows consoles default to cp1252,
    # which raises UnicodeEncodeError on the first card that reaches a log.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

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
