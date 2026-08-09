"""Build stable, PII-scrubbed ScreenContext fixtures from a Nazario mbox.

The input is treated as untrusted text. No extracted URL is requested or opened.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import mailbox
import re
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
LONG_DIGITS = re.compile(r"\b\d{7,}\b")
SPACE = re.compile(r"\s+")


class ContextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._anchor: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._anchor = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self._href is not None:
            self._anchor.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((" ".join(self._anchor), self._href))
            self._href = None
            self._anchor = []


def scrub(value: str) -> str:
    value = EMAIL.sub("redacted@example.invalid", html.unescape(value))
    value = LONG_DIGITS.sub("[digits-redacted]", value)
    return SPACE.sub(" ", value).strip()


def snapshot_url(value: str) -> str:
    """Retain signal-bearing scheme/host but remove live path, query, fragment."""
    try:
        parsed = urlsplit(html.unescape(value.strip()))
    except ValueError:
        return ""
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return ""
    try:
        port = f":{parsed.port}" if parsed.port else ""
    except ValueError:
        port = ""
    return urlunsplit((parsed.scheme.lower(), f"{parsed.hostname.lower()}{port}", "/snapshot", "", ""))


def bodies(message: Message) -> tuple[str, str]:
    plain: list[str] = []
    rich: list[str] = []
    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        if part.get_content_maintype() == "multipart":
            continue
        kind = part.get_content_type()
        if kind not in {"text/plain", "text/html"}:
            continue
        try:
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace") if payload else ""
        except (LookupError, UnicodeError):
            decoded = ""
        (rich if kind == "text/html" else plain).append(decoded)
    return "\n".join(plain), "\n".join(rich)


def context_for(message: Message) -> dict[str, object] | None:
    plain, rich = bodies(message)
    parser = ContextHTMLParser()
    try:
        parser.feed(rich)
    except Exception:
        pass
    text = scrub(" ".join([message.get("Subject", ""), plain, " ".join(parser.text)]))[:6000]
    links = []
    for anchor, href in parser.links:
        stable = snapshot_url(href)
        if stable:
            links.append([scrub(anchor)[:300], stable])
    sender = scrub(message.get("From", ""))
    address_match = re.search(r"@([A-Z0-9.-]+)", message.get("From", ""), re.I)
    from_address = f"redacted@{address_match.group(1).lower()}" if address_match else None
    if not text or not (links or from_address):
        return None
    fingerprint = hashlib.sha256(message.as_bytes()).hexdigest()[:12]
    return {
        "id": f"nazario-{fingerprint}",
        "label": "attack",
        "source": "Nazario phishing corpus (public mbox)",
        "context": {
            "text": text,
            "links": links[:30],
            "from_display": sender[:200] or None,
            "from_address": from_address,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mbox", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--limit", type=int, default=60)
    args = parser.parse_args()
    records = []
    for message in mailbox.mbox(args.mbox, create=False):
        record = context_for(message)
        if record:
            records.append(record)
        if len(records) >= args.limit:
            break
    if len(records) < args.limit:
        raise SystemExit(f"only parsed {len(records)} usable messages")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"wrote {len(records)} ScreenContext snapshots to {args.output}")


if __name__ == "__main__":
    main()
