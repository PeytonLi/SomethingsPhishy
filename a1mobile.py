"""Failure-safe client for placing guardian calls through A1 Mobile."""

from dataclasses import dataclass
import os
import re

import requests


DEFAULT_BASE_URL = "https://hack.a1mobile.com"


@dataclass(frozen=True)
class CallResult:
    """The user-facing outcome of an attempted guardian call."""

    placed: bool
    message: str


def normalize_guardian_phone(phone: str) -> str:
    """Normalize a US ten-digit number to E.164, rejecting invalid input."""

    if not isinstance(phone, str) or not phone.strip():
        raise ValueError("Guardian phone number is missing or invalid.")

    candidate = phone.strip()
    if re.search(r"[A-Za-z]", candidate) or not re.fullmatch(r"[+()\-.\s\d]+", candidate):
        raise ValueError("Guardian phone number must be a valid US number.")

    digits = re.sub(r"\D", "", candidate)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] in "01" or digits[3] in "01":
        raise ValueError("Guardian phone number must be a valid US ten-digit number.")

    return f"+1{digits}"


def _api_rejection_message(response: requests.Response) -> str:
    if response.status_code in (401, 403):
        return "The guardian number or team access may not be verified. Please verify it and try again."

    try:
        payload = response.json()
    except (ValueError, TypeError):
        payload = None

    if isinstance(payload, dict):
        detail = payload.get("message") or payload.get("error") or payload.get("detail")
        if isinstance(detail, str) and "verif" in detail.lower():
            return "The guardian number is not verified. Please verify it and try again."

    return "The guardian call could not be placed. Please try again later."


def place_guardian_call(timeout: float = 5) -> CallResult:
    """Place a guardian call using configuration from environment variables."""

    team_key = os.getenv("A1MOBILE_TEAM_KEY", "").strip()
    configured_phone = os.getenv("A1MOBILE_GUARDIAN_PHONE", "").strip()
    base_url = os.getenv("A1MOBILE_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL

    if not team_key:
        return CallResult(False, "Guardian calling is not configured.")

    try:
        phone = normalize_guardian_phone(configured_phone)
    except ValueError as exc:
        return CallResult(False, str(exc))

    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/calls",
            headers={"X-Team-Key": team_key},
            json={"to": phone},
            timeout=timeout,
        )
    except requests.RequestException:
        return CallResult(False, "The guardian call service is unavailable. Please try again later.")
    except Exception:
        return CallResult(False, "The guardian call could not be placed. Please try again later.")

    if 200 <= response.status_code < 300:
        return CallResult(True, "Guardian call placed successfully.")

    return CallResult(False, _api_rejection_message(response))
