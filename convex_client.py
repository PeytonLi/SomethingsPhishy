"""Failure-tolerant, privacy-preserving access to Convex enrichment."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
from concurrent.futures import Future, ThreadPoolExecutor, wait
from typing import Any
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)
_DEFAULT_TIMEOUT = 1.5
_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)
_client: Any | None = None
_client_lock = threading.Lock()
_record_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="convex-record")


def _get_client() -> Any | None:
    """Create the SDK client lazily so Convex remains optional."""
    global _client
    if _client is not None:
        return _client
    convex_url = os.environ.get("CONVEX_URL", "").strip()
    if not convex_url:
        return None
    with _client_lock:
        if _client is None:
            try:
                from convex import ConvexClient
                _client = ConvexClient(convex_url)
            except Exception:
                logger.warning("Convex client unavailable", exc_info=True)
                return None
    return _client


def _safe_domain(value: Any) -> str | None:
    """Return a normalized DNS domain, rejecting other sensitive data."""
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower().rstrip(".")
    if "://" in candidate:
        candidate = (urlsplit(candidate).hostname or "").rstrip(".")
    try:
        candidate = candidate.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    return candidate if _DOMAIN_RE.fullmatch(candidate) else None


def _safe_codes(codes: Any) -> list[str]:
    if not isinstance(codes, (list, tuple, set)):
        return []
    return [code for code in codes if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code)]


def _text_hash(text: Any) -> str | None:
    if not isinstance(text, str) or not text:
        return None
    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def enrich(domain: str, timeout: float = _DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Fetch intel and community data without raising or exceeding 1.5s."""
    safe_domain = _safe_domain(domain)
    client = _get_client()
    if safe_domain is None or client is None:
        return {}
    try:
        deadline = max(0.0, min(float(timeout), _DEFAULT_TIMEOUT))
    except (TypeError, ValueError):
        deadline = _DEFAULT_TIMEOUT

    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="convex-enrich")
    query_payload = {"domain": safe_domain}
    logger.debug("Convex outbound payload: %r", query_payload)
    logger.debug("Convex outbound payload: %r", query_payload)
    calls: dict[Future[Any], str] = {
        executor.submit(client.query, "intel:getDomainIntel", query_payload): "intel",
        executor.submit(client.query, "community:getCommunityFlag", query_payload): "community",
    }
    try:
        done, pending = wait(calls, timeout=deadline)
        result: dict[str, Any] = {}
        for future in done:
            try:
                value = future.result()
                if value is not None:
                    result[calls[future]] = value
            except Exception:
                logger.warning("Convex %s lookup failed", calls[future], exc_info=True)
        for future in pending:
            future.cancel()
        if pending and result:
            result["reducedConfidence"] = True
        return result
    except Exception:
        logger.warning("Convex enrichment failed", exc_info=True)
        return {}
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _record(
    client: Any,
    payload: dict[str, Any],
    report_danger: bool,
    screenshot: bytes | None = None,
) -> None:
    try:
        if screenshot:
            import requests

            upload_url = client.mutation("scans:generateScreenshotUploadUrl", {})
            response = requests.post(
                upload_url,
                data=screenshot,
                headers={"Content-Type": "image/webp"},
                timeout=5,
            )
            response.raise_for_status()
            storage_id = response.json().get("storageId")
            if isinstance(storage_id, str) and storage_id:
                payload["screenshotId"] = storage_id
        client.mutation("scans:recordScan", payload)
        if report_danger and payload.get("domain"):
            client.mutation("community:reportDanger", {
                "domain": payload["domain"],
                "codes": payload["findingCodes"],
                "userId": payload["userId"],
            })
    except Exception:
        logger.warning("Convex scan recording failed", exc_info=True)


# Codes whose evidence quotes something local and secret. The clipboard
# routinely holds passwords, so its contents must never leave the machine —
# the code and title still tell the guardian everything they need.
_EVIDENCE_WITHHELD = {"CLIPBOARD_PAYLOAD"}


def _safe_findings(findings: Any) -> list[dict[str, Any]]:
    """Shape findings for scans.findingsRedacted, dropping local secrets."""
    out: list[dict[str, Any]] = []
    for item in findings or []:
        if not isinstance(item, dict) or not item.get("code"):
            continue
        code = str(item["code"])
        evidence = str(item.get("evidence", ""))
        out.append({
            "code": code,
            "severity": int(item.get("severity", 0) or 0),
            "title": str(item.get("title", "")),
            "evidence": "[withheld: local clipboard contents]"
                        if code in _EVIDENCE_WITHHELD else evidence,
        })
    return out


def record_scan(
    verdict: str,
    codes: list[str],
    domain: str | None = None,
    *,
    surface: str = "any",
    findings: Any = None,
    user_id: str | None = None,
    text: str | None = None,
    text_hash: str | None = None,
    screenshot: bytes | None = None,
    **_ignored: Any,
) -> None:
    """Queue an allowlisted scan payload without blocking or raising."""
    try:
        client = _get_client()
        if client is None or verdict not in {"SAFE", "CAUTION", "DANGER"}:
            return
        # Field names mirror convex/scans.ts recordScan exactly. A mismatch here
        # is silent from Python's side but rejected by the server validator.
        payload: dict[str, Any] = {
            "userId": user_id or os.environ.get("SP_USER_ID", "margaret-demo"),
            "surface": str(surface or "any"),
            "verdict": verdict,
            "findingCodes": _safe_codes(codes),
            "findingsRedacted": _safe_findings(findings),
        }
        safe_domain = _safe_domain(domain)
        if safe_domain:
            payload["domain"] = safe_domain
        digest = _text_hash(text)
        if digest is None and isinstance(text_hash, str) and re.fullmatch(r"[0-9a-fA-F]{64}", text_hash):
            digest = text_hash.lower()
        if digest:
            payload["textHash"] = digest
        logger.debug("Convex outbound payload: %r", payload)
        safe_screenshot = screenshot if isinstance(screenshot, bytes) and len(screenshot) <= 5_000_000 else None
        _record_executor.submit(
            _record,
            client,
            payload,
            verdict == "DANGER",
            safe_screenshot,
        )
    except Exception:
        logger.warning("Could not queue Convex scan", exc_info=True)
