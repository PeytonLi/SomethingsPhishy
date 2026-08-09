"""
signals.py — deterministic signal extraction for a screen-context scam checker.

Design contract:
    Every check returns Finding objects containing HARD EVIDENCE (the actual
    strings observed), never a vague label. The LLM layer downstream is only
    allowed to *explain* these findings, never to invent new ones. This is what
    keeps the verdict trustworthy and the false-positive rate low.

Surfaces covered: email, web checkout (incl. Stripe), crypto payment prompts.
"""

from __future__ import annotations

import re

import tldextract

from data.brands import ESP_TRACKING_DOMAINS, GENERIC_ESP_TRACKING_DOMAINS
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Iterable, Optional
from urllib.parse import urlparse, urlunparse

# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------


class Severity(IntEnum):
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Verdict(IntEnum):
    SAFE = 0
    CAUTION = 1
    DANGER = 2


@dataclass
class Finding:
    code: str                 # stable id, e.g. "LINK_TEXT_HREF_MISMATCH"
    severity: Severity
    title: str                # short, human, no jargon
    evidence: str             # the ACTUAL observed strings — quote them
    surface: str              # "email" | "web" | "crypto" | "any"

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": int(self.severity),
            "title": self.title,
            "evidence": self.evidence,
            "surface": self.surface,
        }


@dataclass
class ScreenContext:
    """Whatever the VoiceOS integration can hand us. All fields optional so the
    module degrades gracefully when a surface exposes less than we'd like."""
    text: str = ""
    # (anchor_text, href) pairs — the single highest-signal email input
    links: list[tuple[str, str]] = field(default_factory=list)
    page_url: Optional[str] = None
    iframe_origins: list[str] = field(default_factory=list)
    # email headers
    from_display: Optional[str] = None
    from_address: Optional[str] = None
    reply_to: Optional[str] = None
    # crypto
    displayed_address: Optional[str] = None   # address shown on screen
    clipboard_address: Optional[str] = None   # what's actually pasted/queued
    prior_addresses: list[str] = field(default_factory=list)
    # downloads
    download_url: Optional[str] = None        # href behind the download button
    download_filename: Optional[str] = None   # actual filename served
    download_button_text: Optional[str] = None  # what the button PROMISES
    content_type: Optional[str] = None        # server MIME, if observable
    file_size_bytes: Optional[int] = None
    clipboard_text: str = ""
    download_host_url: Optional[str] = None
    download_referrer_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

# Brands most impersonated in phishing. Keep short; precision > recall here.
IMPERSONATED_BRANDS = {
    "paypal": "paypal.com",
    "apple": "apple.com",
    "microsoft": "microsoft.com",
    "amazon": "amazon.com",
    "netflix": "netflix.com",
    "chase": "chase.com",
    "wellsfargo": "wellsfargo.com",
    "bankofamerica": "bankofamerica.com",
    "coinbase": "coinbase.com",
    "metamask": "metamask.io",
    "phantom": "phantom.app",
    "ledger": "ledger.com",
    "binance": "binance.com",
    "stripe": "stripe.com",
    "docusign": "docusign.com",
    "fedex": "fedex.com",
    "usps": "usps.com",
    "irs": "irs.gov",
}

# Stripe-owned origins. A real Stripe payment field is same-origin with one of
# these; a cloned checkout renders its own form on the attacker's domain.
STRIPE_ORIGINS = {"js.stripe.com", "checkout.stripe.com", "hooks.stripe.com",
                  "m.stripe.network", "b.stripecdn.com"}

# Homoglyph folds: characters attackers substitute to build lookalike domains.
HOMOGLYPHS = {
    "0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t",
    "а": "a", "е": "e", "о": "o", "р": "p",
    "с": "c", "х": "x", "у": "y", "і": "i",
    "vv": "w",
}

SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
              "buff.ly", "cutt.ly", "rb.gy", "shorturl.at"}

FREE_MAIL = {"gmail.com", "outlook.com", "hotmail.com", "yahoo.com",
             "proton.me", "protonmail.com", "aol.com", "mail.com", "gmx.com"}

# Software whose download pages are heavily typosquatted / malvertised.
# (regex matching how it appears on screen, display name, legitimate domains)
OFFICIAL_SOFTWARE = [
    (r"notepad\s*\+\+|notepad[- ]?plus[- ]?plus", "Notepad++", {"notepad-plus-plus.org"}),
    (r"\bvlc\b|videolan", "VLC", {"videolan.org"}),
    (r"\b7[- ]?zip\b", "7-Zip", {"7-zip.org"}),
    (r"\bwinrar\b", "WinRAR", {"rarlab.com", "win-rar.com"}),
    (r"\bobs studio\b|\bobs\b", "OBS Studio", {"obsproject.com"}),
    (r"\baudacity\b", "Audacity", {"audacityteam.org"}),
    (r"\bblender\b", "Blender", {"blender.org"}),
    (r"\bgimp\b", "GIMP", {"gimp.org"}),
    (r"\bfilezilla\b", "FileZilla", {"filezilla-project.org"}),
    (r"\bhandbrake\b", "HandBrake", {"handbrake.fr"}),
    (r"\brufus\b", "Rufus", {"rufus.ie"}),
    (r"\bkeepass\b", "KeePass", {"keepass.info"}),
    (r"\blibreoffice\b", "LibreOffice", {"libreoffice.org", "documentfoundation.org"}),
    (r"google chrome|\bchrome browser\b", "Chrome", {"google.com", "chrome.com"}),
    (r"\bfirefox\b|\bmozilla\b", "Firefox", {"mozilla.org", "mozilla.net"}),
    (r"\bzoom\b", "Zoom", {"zoom.us", "zoom.com"}),
    (r"\bdiscord\b", "Discord", {"discord.com", "discordapp.com"}),
    (r"\btelegram\b", "Telegram", {"telegram.org", "t.me"}),
    (r"\bsignal\b", "Signal", {"signal.org"}),
    (r"\bsteam\b", "Steam", {"steampowered.com", "valvesoftware.com"}),
    (r"\banydesk\b", "AnyDesk", {"anydesk.com"}),
    (r"\bteamviewer\b", "TeamViewer", {"teamviewer.com"}),
    (r"\bmalwarebytes\b", "Malwarebytes", {"malwarebytes.com"}),
    (r"\bccleaner\b", "CCleaner", {"ccleaner.com", "piriform.com"}),
    (r"adobe (acrobat|reader)", "Adobe Acrobat", {"adobe.com"}),
    (r"\bpython\b", "Python", {"python.org"}),
    (r"node\.?js", "Node.js", {"nodejs.org"}),
    (r"\bdocker\b", "Docker", {"docker.com"}),
]

# Hosts where a legitimate binary plausibly lives. Deliberately conservative —
# generic CDNs are omitted because attackers use them just as freely.
TRUSTED_DOWNLOAD_HOSTS = {
    "github.com", "githubusercontent.com", "githubassets.com",
    "sourceforge.net", "microsoft.com", "windows.net", "aka.ms",
    "google.com", "gstatic.com", "googleapis.com",
    "apple.com", "mozilla.org", "mozilla.net", "python.org", "npmjs.com",
}

# Extensions that can execute code on open.
DANGEROUS_EXT = {
    "exe", "scr", "com", "pif", "bat", "cmd", "msi", "msix", "vbs", "vbe",
    "js", "jse", "wsf", "wsh", "hta", "ps1", "psm1", "reg", "cpl", "lnk",
    "inf", "msc", "jar", "gadget", "application",
    "dmg", "pkg", "command", "app",          # macOS
    "apk", "xapk", "ipa",                     # mobile
}

# Container formats used to smuggle payloads past "downloaded from the
# internet" warnings — a real invoice is never shipped as a disk image.
MOTW_EVASION_EXT = {"iso", "img", "vhd", "vhdx", "cab"}

ARCHIVE_EXT = {"zip", "rar", "7z", "tar", "gz", "tgz"}

# Words implying the download is a harmless document, not a program.
DOC_PROMISE = (r"(pdf|document|invoice|receipt|statement|report|resume|cv|"
               r"photo|image|picture|spreadsheet|form|contract|manual|"
               r"guide|e-?book|ticket|certificate)")

# ---------------------------------------------------------------------------
# Pattern banks
# ---------------------------------------------------------------------------

URGENCY_PATTERNS = [
    (r"\b(within|in)\s+(24|48|72)\s*hours?\b", "a countdown deadline"),
    (r"\b(immediate(ly)?|urgent(ly)?|act now|right away)\b", "urgency language"),
    (r"\b(suspend(ed)?|clos(e|ing|ed)|lock(ed)?|terminat(e|ed)|deactivat)\w*\b"
     r"[^.]{0,40}\b(account|access|card)\b", "a threat to your account"),
    (r"\bfinal (notice|warning|reminder)\b", "a 'final notice' threat"),
    (r"\b(legal action|arrest|lawsuit|warrant)\b", "threat of legal trouble"),
]

CREDENTIAL_PATTERNS = [
    (r"\b(verify|confirm|update|re-?enter)\b[^.]{0,30}"
     r"\b(password|login|credentials|account details)\b", "asks you to re-enter your password"),
    (r"\b(one[- ]?time (code|passcode|password)|OTP|2FA|verification code|security code)\b",
     "asks for a verification code"),
    (r"\b(social security|SSN|national insurance)\b", "asks for a Social Security number"),
    (r"\b(anydesk|teamviewer|remote desktop|screen ?share)\b",
     "asks you to install remote-access software"),
]

# Irreversible payment rails — legitimate businesses rarely demand these.
IRREVERSIBLE_RAILS = [
    (r"\bgift ?cards?\b", "gift cards"),
    (r"\b(apple|google play|steam|itunes) ?(gift ?)?cards?\b", "store gift cards"),
    (r"\bwire transfer\b", "a wire transfer"),
    (r"\b(zelle|venmo|cash ?app)\b", "an instant payment app"),
    (r"\b(bitcoin|btc|ethereum|eth|usdt|crypto(currency)?)\b[^.]{0,40}\b(send|pay|transfer|deposit)\b",
     "a crypto transfer"),
    (r"\b(bitcoin|crypto) ?atm\b", "a crypto ATM"),
]

SECRECY_PATTERNS = [
    (r"\b(do not|don'?t)\b[^.]{0,30}\b(tell|inform|discuss|mention|share)\b",
     "instructs you to keep it secret"),
    (r"\bkeep (this|it) (confidential|between us|secret|private)\b",
     "asks you to stay quiet about it"),
    (r"\b(bank|teller|family|police)\b[^.]{0,30}\bmay (try to )?(stop|prevent|discourage)\b",
     "warns you that your bank or family will try to stop you"),
]

# Crypto-specific. Seed-phrase solicitation is near-zero false positive.
SEED_PHRASE_PATTERNS = [
    (r"\b(seed|recovery|mnemonic|secret) ?phrase\b", "asks for your recovery phrase"),
    (r"\b(12|24)[- ]word\b", "asks for your 12/24-word phrase"),
    (r"\bprivate key\b", "asks for your private key"),
    (r"\b(sync|validate|restore|import|verify) (your )?wallet\b",
     "asks you to 'validate' or 'sync' your wallet"),
]

GIVEAWAY_PATTERNS = [
    (r"\bsend\b[^.]{0,25}\breceive\b[^.]{0,25}\b(double|2x|twice|back)\b",
     "promises to send back double what you pay"),
    (r"\b(giveaway|airdrop)\b[^.]{0,40}\b(claim|connect wallet)\b",
     "a giveaway or airdrop that wants your wallet"),
    (r"\bguaranteed (returns?|profits?)\b", "guarantees returns"),
]

APPROVAL_PATTERNS = [
    (r"\bsetApprovalForAll\b", "grants access to ALL your NFTs"),
    (r"\b(unlimited|infinite) (approval|allowance|spend)\b",
     "grants unlimited spending access to your tokens"),
    (r"\bincreaseAllowance\b", "increases how much a contract can spend"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _host(url: str) -> str:
    try:
        h = (urlparse(url).hostname or "").lower()
        return h[4:] if h.startswith("www.") else h
    except ValueError:
        return ""


_TLD_EXTRACT = tldextract.TLDExtract(suffix_list_urls=())


def registrable(host: str) -> str:
    """Return the registrable domain using the bundled public suffix list."""
    if not host:
        return ""
    extracted = _TLD_EXTRACT(host.lower().strip("."))
    return extracted.top_domain_under_public_suffix or extracted.domain


def _fold(s: str) -> str:
    """Normalize homoglyphs so `paypa1` and `pаypal` fold to `paypal`."""
    s = s.lower()
    for src, dst in HOMOGLYPHS.items():
        s = s.replace(src, dst)
    return s


def _levenshtein(a: str, b: str, cap: int = 3) -> int:
    """Bounded edit distance — early-exits once past `cap`."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def _find(patterns: Iterable[tuple[str, str]], text: str) -> list[tuple[str, str]]:
    """Return (matched_text, description) for each pattern that fires."""
    out = []
    for rx, desc in patterns:
        m = re.search(rx, text, re.I)
        if m:
            out.append((m.group(0).strip(), desc))
    return out


# ---------------------------------------------------------------------------
# Checks — links & domains
# ---------------------------------------------------------------------------

def check_link_mismatch(ctx: ScreenContext) -> list[Finding]:
    """Anchor text claims one domain, href points somewhere else.
    Highest-signal check available for email phishing."""
    out = []
    for text, href in ctx.links:
        claimed = re.search(r"\b((?:[\w-]+\.)+[a-z]{2,})\b", text or "", re.I)
        if not claimed:
            continue
        claimed_dom = registrable(claimed.group(1).lower())
        actual_dom = registrable(_host(href))
        if not actual_dom or claimed_dom == actual_dom:
            continue
        allowed = ESP_TRACKING_DOMAINS.get(claimed_dom, set())
        if actual_dom in allowed or actual_dom in GENERIC_ESP_TRACKING_DOMAINS:
            continue
        out.append(Finding(
            code="LINK_TEXT_HREF_MISMATCH",
            severity=Severity.CRITICAL,
            title="A link goes somewhere different than it says",
            evidence=f"The link reads “{claimed_dom}” but actually opens “{actual_dom}”.",
            surface="email",
        ))
    return out


def check_lookalike_domain(ctx: ScreenContext) -> list[Finding]:
    """Domain is a near-miss of an impersonated brand (typo or homoglyph)."""
    out, seen = [], set()
    hosts = [_host(h) for _, h in ctx.links]
    if ctx.page_url:
        hosts.append(_host(ctx.page_url))
    if ctx.from_address and "@" in ctx.from_address:
        hosts.append(ctx.from_address.split("@")[-1].lower())

    for host in filter(None, hosts):
        dom = registrable(host)
        if dom in seen:
            continue
        seen.add(dom)
        label = dom.split(".")[0]
        folded = _fold(label)
        exact_folds = {folded, folded.replace("rn", "m")}
        for brand, real in IMPERSONATED_BRANDS.items():
            if dom == real:
                break
            # Multi-character folds are only safe for exact brand matches;
            # applying them before fuzzy matching mangles ordinary labels.
            if brand in exact_folds and label != brand:
                out.append(Finding(
                    code="HOMOGLYPH_DOMAIN",
                    severity=Severity.CRITICAL,
                    title=f"The address imitates {brand.title()} using swapped characters",
                    evidence=f"“{dom}” is designed to look like “{real}” — it is not.",
                    surface="any"))
                break
            if 0 < _levenshtein(folded, brand) <= 1 and len(brand) >= 5:
                out.append(Finding(
                    code="LOOKALIKE_DOMAIN",
                    severity=Severity.HIGH,
                    title=f"The address is one character off from {brand.title()}",
                    evidence=f"“{dom}” closely imitates the real “{real}”.",
                    surface="any"))
                break
            # Brand appears as a subdomain of an unrelated site:
            # paypal.secure-login.xyz  ->  the real owner is secure-login.xyz
            if host.startswith(f"{brand}.") and dom != real:
                out.append(Finding(
                    code="BRAND_AS_SUBDOMAIN",
                    severity=Severity.HIGH,
                    title=f"“{brand.title()}” appears in the address but the site is owned by someone else",
                    evidence=f"“{host}” is actually controlled by “{dom}”, not {real}.",
                    surface="any"))
                break
    return out


def check_url_hygiene(ctx: ScreenContext) -> list[Finding]:
    out = []
    for _, href in ctx.links:
        host = _host(href)
        if not host:
            continue
        if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host):
            out.append(Finding("RAW_IP_URL", Severity.HIGH,
                               "A link points at a bare IP address",
                               f"“{host}” — legitimate companies use named domains.", "any"))
        if "xn--" in host:
            out.append(Finding("PUNYCODE_DOMAIN", Severity.HIGH,
                               "A link uses disguised international characters",
                               f"“{host}” encodes characters that can mimic normal letters.", "any"))
        if registrable(host) in SHORTENERS:
            out.append(Finding("SHORTENED_URL", Severity.MEDIUM,
                               "A link is hidden behind a shortener",
                               f"“{host}” conceals the real destination.", "any"))
        if href.lower().startswith("http://") and re.search(
                r"\b(login|signin|verify|account|bank|pay)\b", href, re.I):
            out.append(Finding("INSECURE_LOGIN_LINK", Severity.HIGH,
                               "A sign-in link is not encrypted",
                               f"“{href[:60]}” uses http, not https.", "any"))
    return out


# ---------------------------------------------------------------------------
# Checks — email headers
# ---------------------------------------------------------------------------

def check_sender(ctx: ScreenContext) -> list[Finding]:
    out = []
    addr = (ctx.from_address or "").lower()
    domain = addr.split("@")[-1] if "@" in addr else ""

    if ctx.from_display and domain:
        disp = _fold(ctx.from_display)
        for brand, real in IMPERSONATED_BRANDS.items():
            if brand in disp.replace(" ", "") and registrable(domain) != real:
                sev = Severity.CRITICAL if registrable(domain) in FREE_MAIL else Severity.HIGH
                out.append(Finding(
                    "DISPLAY_NAME_SPOOF", sev,
                    f"The sender name says {brand.title()} but the email isn't from them",
                    f"Shown as “{ctx.from_display}”, actually sent from “{addr}”.",
                    "email"))
                break

    if ctx.reply_to and domain:
        rt_domain = ctx.reply_to.split("@")[-1].lower()
        if registrable(rt_domain) != registrable(domain):
            out.append(Finding(
                "REPLY_TO_MISMATCH", Severity.HIGH,
                "Replies would go to a different company",
                f"Sent from “{domain}” but replies go to “{rt_domain}”.",
                "email"))
    return out


def check_domain_age(domain: str, created: Optional[datetime]) -> list[Finding]:
    """Feed `created` from an RDAP lookup (rdap.org/domain/<d>). A bank domain
    registered last week is about as close to proof as this tool gets."""
    if not created:
        return []
    days = (datetime.now(timezone.utc) - created).days
    if days <= 30:
        return [Finding("DOMAIN_VERY_NEW", Severity.CRITICAL,
                        "This website was created days ago",
                        f"“{domain}” was registered {days} day(s) ago. "
                        f"Real companies' sites are years old.", "any")]
    if days <= 180:
        return [Finding("DOMAIN_NEW", Severity.MEDIUM,
                        "This website is only a few months old",
                        f"“{domain}” was registered {days} days ago.", "any")]
    return []


# ---------------------------------------------------------------------------
# Checks — checkout / Stripe
# ---------------------------------------------------------------------------

def check_checkout(ctx: ScreenContext) -> list[Finding]:
    """A genuine Stripe checkout renders card fields inside a Stripe-owned
    origin. A cloned one renders a plain form on the attacker's own domain
    while displaying Stripe branding."""
    out = []
    text = ctx.text or ""
    page_host = _host(ctx.page_url or "")
    page_dom = registrable(page_host)
    origins = {registrable(_host(o if "//" in o else f"https://{o}"))
               for o in ctx.iframe_origins}
    stripe_present = any(
        registrable(s) in origins or s in {_host(o if "//" in o else f"https://{o}")
                                           for o in ctx.iframe_origins}
        for s in STRIPE_ORIGINS)

    claims_stripe = re.search(r"\b(powered by stripe|stripe)\b", text, re.I)
    asks_for_card = re.search(
        r"\b(card number|cvv|cvc|expiry|expiration|security code)\b", text, re.I)

    if claims_stripe and asks_for_card and not stripe_present and page_dom:
        out.append(Finding(
            "FAKE_PAYMENT_PROCESSOR", Severity.CRITICAL,
            "This page shows Stripe branding but isn't using Stripe",
            f"Card fields are hosted by “{page_dom}” itself, not by Stripe. "
            f"A real Stripe checkout loads its payment fields from stripe.com.",
            "web"))

    if asks_for_card and ctx.page_url and ctx.page_url.lower().startswith("http://"):
        out.append(Finding(
            "INSECURE_PAYMENT_PAGE", Severity.CRITICAL,
            "This payment page is not encrypted",
            f"“{page_host}” is served over http — card details would be sent in the clear.",
            "web"))

    # Brand shown on the page vs. who actually owns the checkout domain.
    if asks_for_card and page_dom:
        for brand, real in IMPERSONATED_BRANDS.items():
            if re.search(rf"\b{re.escape(brand)}\b", text, re.I) and page_dom != real:
                out.append(Finding(
                    "CHECKOUT_BRAND_MISMATCH", Severity.HIGH,
                    f"The page mentions {brand.title()} but payment goes to another site",
                    f"You are entering card details on “{page_dom}”, not {real}.",
                    "web"))
                break
    return out


# ---------------------------------------------------------------------------
# Checks — crypto
# ---------------------------------------------------------------------------

def check_crypto(ctx: ScreenContext) -> list[Finding]:
    out = []
    text = ctx.text or ""

    for matched, desc in _find(SEED_PHRASE_PATTERNS, text):
        out.append(Finding(
            "SEED_PHRASE_REQUEST", Severity.CRITICAL,
            "Something here is asking for your wallet recovery phrase",
            f"Found: “{matched}”. No legitimate wallet, exchange, or support "
            f"agent ever needs it. Anyone who has it can take everything.",
            "crypto"))
        break

    for matched, desc in _find(GIVEAWAY_PATTERNS, text):
        out.append(Finding("CRYPTO_GIVEAWAY", Severity.CRITICAL,
                           "This is a classic giveaway scam pattern",
                           f"Found: “{matched}” — it {desc}.", "crypto"))
        break

    for matched, desc in _find(APPROVAL_PATTERNS, text):
        out.append(Finding("DANGEROUS_APPROVAL", Severity.HIGH,
                           "This transaction hands over broad spending access",
                           f"“{matched}” — it {desc}.", "crypto"))

    # Address poisoning: shown address != address actually being sent to.
    shown = (ctx.displayed_address or "").strip()
    actual = (ctx.clipboard_address or "").strip()
    if shown and actual and shown.lower() != actual.lower():
        out.append(Finding(
            "ADDRESS_MISMATCH", Severity.CRITICAL,
            "The destination address changed",
            f"Screen shows “{shown[:10]}…{shown[-6:]}” but the transaction "
            f"would send to “{actual[:10]}…{actual[-6:]}”.",
            "crypto"))

    # Lookalike of a previously used address — first/last chars match, middle doesn't.
    target = actual or shown
    if target:
        for prior in ctx.prior_addresses:
            p = prior.strip()
            if p.lower() == target.lower():
                continue
            if (len(p) == len(target) and p[:4].lower() == target[:4].lower()
                    and p[-4:].lower() == target[-4:].lower()):
                out.append(Finding(
                    "ADDRESS_POISONING", Severity.CRITICAL,
                    "This address is a decoy of one you used before",
                    f"It starts and ends like “{p[:6]}…{p[-4:]}” but the middle "
                    f"is different. Attackers plant these in your history.",
                    "crypto"))
                break
    return out


# ---------------------------------------------------------------------------
# Checks — content / social engineering
# ---------------------------------------------------------------------------

def check_content(ctx: ScreenContext) -> list[Finding]:
    out, text = [], ctx.text or ""

    urgency = _find(URGENCY_PATTERNS, text)
    if urgency:
        matched, desc = urgency[0]
        out.append(Finding("URGENCY_PRESSURE", Severity.MEDIUM,
                           "It's pressuring you to act fast",
                           f"“{matched}” — {desc}. Pressure is how scams stop you thinking.",
                           "any"))

    for matched, desc in _find(CREDENTIAL_PATTERNS, text):
        out.append(Finding("CREDENTIAL_REQUEST", Severity.HIGH,
                           "It's asking for information no real company asks for",
                           f"“{matched}” — it {desc}.", "any"))

    for matched, desc in _find(IRREVERSIBLE_RAILS, text):
        out.append(Finding("IRREVERSIBLE_PAYMENT", Severity.HIGH,
                           "It wants payment in a form you can't get back",
                           f"“{matched}” — it asks for {desc}. "
                           f"These payments cannot be reversed.", "any"))

    for matched, desc in _find(SECRECY_PATTERNS, text):
        out.append(Finding("SECRECY_INSTRUCTION", Severity.CRITICAL,
                           "It's telling you to keep this secret",
                           f"“{matched}” — it {desc}. Real institutions never do this.",
                           "any"))
    return out


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

# Codes that alone justify a DANGER verdict — evidence, not vibes.
DECISIVE = {
    "LINK_TEXT_HREF_MISMATCH", "HOMOGLYPH_DOMAIN", "SEED_PHRASE_REQUEST",
    "ADDRESS_MISMATCH", "ADDRESS_POISONING", "FAKE_PAYMENT_PROCESSOR",
    "SECRECY_INSTRUCTION", "CRYPTO_GIVEAWAY", "INSECURE_PAYMENT_PAGE",
    "DOMAIN_VERY_NEW",
}


def analyze(ctx: ScreenContext,
            domain_created: Optional[datetime] = None) -> dict:
    findings: list[Finding] = []
    for check in (check_link_mismatch, check_lookalike_domain, check_url_hygiene,
                  check_sender, check_checkout, check_crypto, check_content):
        try:
            findings.extend(check(ctx))
        except Exception:
            continue  # never let one check take down the verdict

    if domain_created and ctx.page_url:
        findings.extend(check_domain_age(registrable(_host(ctx.page_url)), domain_created))

    # De-dupe by code, keeping the strongest instance.
    best: dict[str, Finding] = {}
    for f in findings:
        if f.code not in best or f.severity > best[f.code].severity:
            best[f.code] = f
    findings = sorted(best.values(), key=lambda f: -f.severity)

    codes = {f.code for f in findings}
    highs = sum(1 for f in findings if f.severity >= Severity.HIGH)

    if codes & DECISIVE or highs >= 2:
        verdict = Verdict.DANGER
    elif highs == 1 or any(f.severity == Severity.MEDIUM for f in findings):
        verdict = Verdict.CAUTION
    else:
        verdict = Verdict.SAFE

    return {
        "verdict": verdict.name,
        # Top 3 only — a wall of warnings is a wall people ignore.
        "findings": [f.as_dict() for f in findings[:3]],
        "finding_count": len(findings),
        "action": _action(verdict, codes),
        "explainable": bool(findings),
    }


def _action(verdict: Verdict, codes: set[str]) -> str:
    """One concrete instruction. Advise — never act on the user's behalf."""
    if verdict is Verdict.SAFE:
        return "Nothing suspicious found. If you're still unsure, contact the company directly."
    if codes & {"SEED_PHRASE_REQUEST", "ADDRESS_MISMATCH", "ADDRESS_POISONING",
                "CRYPTO_GIVEAWAY", "DANGEROUS_APPROVAL"}:
        return ("Do not approve this transaction and never enter your recovery phrase. "
                "Close this window.")
    if codes & {"FAKE_PAYMENT_PROCESSOR", "INSECURE_PAYMENT_PAGE",
                "CHECKOUT_BRAND_MISMATCH"}:
        return ("Do not enter your card details. Go to the seller's real website "
                "yourself and pay there.")
    if verdict is Verdict.DANGER:
        return ("Don't click anything here. Contact the company using the number on "
                "your card or their official app.")
    return "Slow down and verify this independently before you act."
