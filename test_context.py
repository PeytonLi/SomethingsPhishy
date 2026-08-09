from __future__ import annotations

import builtins
import importlib
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parent


def provider_doubles() -> dict[str, object]:
    return {
        "pyperclip": SimpleNamespace(paste=lambda: ""),
        "websocket": SimpleNamespace(create_connection=Mock()),
        "tldextract": SimpleNamespace(TLDExtract=lambda **_kwargs: Mock()),
    }


def context_module() -> ModuleType:
    """Import with inert provider doubles so behavior tests are self-contained."""
    with patch.dict(sys.modules, provider_doubles()):
        return importlib.import_module("context")


def page_target(title: str, url: str) -> dict[str, str]:
    return {
        "type": "page",
        "title": title,
        "url": url,
        "webSocketDebuggerUrl": "ws://mock.test/devtools/page/1",
    }


class OptionalProviderTests(unittest.TestCase):
    def test_module_imports_and_capture_degrades_without_optional_providers(self) -> None:
        optional_roots = {
            "pyperclip",
            "websocket",
            "uiautomation",
            "win32com",
            "PIL",
            "pytesseract",
            "winsdk",
        }
        real_import = builtins.__import__

        def import_without_optional(
            name: str,
            globals: dict[str, Any] | None = None,
            locals: dict[str, Any] | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> Any:
            if name.split(".", 1)[0] in optional_roots:
                raise ModuleNotFoundError(f"blocked optional provider: {name}", name=name)
            return real_import(name, globals, locals, fromlist, level)

        module_name = "_context_without_optional_providers"
        spec = importlib.util.spec_from_file_location(module_name, PROJECT_ROOT / "context.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        self.addCleanup(sys.modules.pop, module_name, None)

        with (
            patch.dict(sys.modules, {"tldextract": provider_doubles()["tldextract"]}),
            patch.object(builtins, "__import__", side_effect=import_without_optional),
        ):
            spec.loader.exec_module(module)

        with (
            patch.object(module, "_recent_downloads", return_value=[]),
            patch.object(module, "_foreground_title", return_value="Native app"),
            patch.object(module, "_cdp_targets", return_value=[]),
            patch.object(module, "_uia_context", return_value=(None, "Native text")),
        ):
            captured = module.capture("page")

        self.assertEqual("Native text", captured.text)


class ForegroundSelectionTests(unittest.TestCase):
    def test_only_a_foreground_matching_cdp_target_is_selected(self) -> None:
        context = context_module()
        foreground = page_target("Inbox - Mail", "https://mail.example.test/inbox")
        unrelated = page_target("Stripe docs", "https://docs.stripe.com/")

        with patch.object(context, "_foreground_title", return_value="Inbox - Mail - Chrome"):
            self.assertIs(foreground, context._pick_target([unrelated, foreground]))

        with (
            patch.object(context, "_foreground_title", return_value="Calculator"),
            self.assertRaises(LookupError),
        ):
            context._pick_target([unrelated, foreground])

    def test_uia_native_text_is_retained_when_cdp_target_is_unrelated(self) -> None:
        context = context_module()
        cdp_dom = Mock(return_value={"text": "Wrong browser tab"})

        with (
            patch.object(context, "_clipboard_text", return_value=""),
            patch.object(context, "_recent_downloads", return_value=[]),
            patch.object(context, "_foreground_title", return_value="Ledger Live"),
            patch.object(
                context,
                "_cdp_targets",
                return_value=[page_target("News", "https://news.example.test/")],
            ),
            patch.object(context, "_cdp_dom", cdp_dom),
            patch.object(context, "_uia_context", return_value=(None, "Ledger native text")),
            patch.object(context, "_ocr_context", return_value=(None, ""), create=True),
        ):
            captured = context.capture("page")

        cdp_dom.assert_not_called()
        self.assertEqual("Ledger native text", captured.text)
        self.assertIsNone(captured.page_url)


class ScreenshotCaptureTests(unittest.TestCase):
    def test_captures_resizes_and_encodes_foreground_window_in_memory(self) -> None:
        context = context_module()
        captured_image = Mock()
        captured_image.size = (1920, 1080)
        resized_image = Mock()
        captured_image.resize.return_value = resized_image
        resized_image.save.side_effect = lambda output, **_kwargs: output.write(b"webp-data")
        image_grab = SimpleNamespace(grab=Mock(return_value=captured_image))
        image_module = SimpleNamespace(
            Resampling=SimpleNamespace(LANCZOS="lanczos"),
        )
        pil_module = SimpleNamespace(Image=image_module, ImageGrab=image_grab)
        bounds = (10, 20, 1930, 1100)

        with (
            patch.object(context, "_foreground_bounds", return_value=bounds),
            patch.dict(sys.modules, {"PIL": pil_module}),
        ):
            result = context.capture_screenshot()

        self.assertEqual(b"webp-data", result)
        image_grab.grab.assert_called_once_with(bbox=bounds)
        captured_image.resize.assert_called_once_with((1440, 810), "lanczos")
        resized_image.save.assert_called_once()
        _, save_kwargs = resized_image.save.call_args
        self.assertEqual("WEBP", save_kwargs["format"])
        self.assertEqual(80, save_kwargs["quality"])

    def test_returns_none_without_foreground_bounds(self) -> None:
        context = context_module()

        with patch.object(context, "_foreground_bounds", return_value=None):
            self.assertIsNone(context.capture_screenshot())

    def test_returns_none_when_image_capture_fails(self) -> None:
        context = context_module()
        image_grab = SimpleNamespace(grab=Mock(side_effect=OSError("capture failed")))
        pil_module = SimpleNamespace(
            Image=SimpleNamespace(Resampling=SimpleNamespace(LANCZOS="lanczos")),
            ImageGrab=image_grab,
        )

        with (
            patch.object(context, "_foreground_bounds", return_value=(0, 0, 800, 600)),
            patch.dict(sys.modules, {"PIL": pil_module}),
        ):
            self.assertIsNone(context.capture_screenshot())


class FallbackAndSurfaceTests(unittest.TestCase):
    def test_ocr_fallback_can_be_exercised_without_real_screenshot_or_ocr(self) -> None:
        context = context_module()
        ocr = Mock(return_value=(None, "Payment requested in rendered canvas"))

        with (
            patch.object(context, "_clipboard_text", return_value=""),
            patch.object(context, "_recent_downloads", return_value=[]),
            patch.object(context, "_cdp_targets", return_value=[]),
            patch.object(context, "_uia_context", return_value=(None, "")),
            patch.object(context, "_ocr_context", ocr, create=True),
        ):
            captured = context.capture("page")

        ocr.assert_called_once_with()
        self.assertEqual("Payment requested in rendered canvas", captured.text)
        self.assertIn("ocr", captured.capture_source)

    def test_downloads_are_excluded_from_page_capture(self) -> None:
        context = context_module()
        downloads = Mock(return_value=[{
            "filename": "invoice.pdf.exe",
            "size_bytes": 1234,
            "zone": {"HostUrl": "https://download.example.test/invoice.pdf.exe"},
        }])
        target = page_target("Example", "https://example.test/")

        with (
            patch.object(context, "_clipboard_text", return_value=""),
            patch.object(context, "_recent_downloads", downloads),
            patch.object(context, "_foreground_title", return_value="Example - Chrome"),
            patch.object(context, "_cdp_targets", return_value=[target]),
            patch.object(context, "_cdp_dom", return_value={"text": "Example", "links": [], "iframes": []}),
        ):
            captured = context.capture("page")

        downloads.assert_not_called()
        self.assertIsNone(captured.download_filename)
        self.assertEqual([], captured.recent_downloads)

    def test_downloads_are_included_for_download_capture(self) -> None:
        context = context_module()
        download = {
            "filename": "setup.exe",
            "size_bytes": 4321,
            "zone": {
                "HostUrl": "https://cdn.example.test/setup.exe",
                "ReferrerUrl": "https://example.test/download",
                "ZoneId": "3",
            },
        }

        with (
            patch.object(context, "_clipboard_text", return_value=""),
            patch.object(context, "_recent_downloads", return_value=[download]),
            patch.object(context, "_cdp_targets", return_value=[]),
            patch.object(context, "_uia_context", return_value=(None, "")),
            patch.object(context, "_ocr_context", return_value=(None, ""), create=True),
        ):
            captured = context.capture("download")

        self.assertEqual("setup.exe", captured.download_filename)
        self.assertEqual(4321, captured.file_size_bytes)
        self.assertEqual("https://cdn.example.test/setup.exe", captured.download_url)
        self.assertEqual([download], captured.recent_downloads)


class SurfaceFieldTests(unittest.TestCase):
    def capture_cdp(self, surface: str, dom: dict[str, Any]):
        context = context_module()
        target = page_target("Checkout", "https://merchant.example.test/checkout")
        with (
            patch.object(context, "_clipboard_text", return_value=""),
            patch.object(context, "_recent_downloads", return_value=[]),
            patch.object(context, "_foreground_title", return_value="Checkout - Chrome"),
            patch.object(context, "_cdp_targets", return_value=[target]),
            patch.object(context, "_cdp_dom", return_value=dom),
        ):
            return context.capture(surface)

    def test_browser_email_keeps_cdp_content_and_email_fields(self) -> None:
        captured = self.capture_cdp("email", {
            "text": "Security notice",
            "links": [["Review activity", "https://account.example.test/review"]],
            "iframes": ["https://mail.example.test"],
            "fromDisplay": "Account Security",
            "fromAddress": "security@example.test",
            "replyTo": "support@example.test",
        })

        self.assertEqual(
            "https://merchant.example.test/checkout",
            captured.page_url,
        )
        self.assertEqual("Security notice", captured.text)
        self.assertEqual(
            [("Review activity", "https://account.example.test/review")],
            captured.links,
        )
        self.assertEqual(["https://mail.example.test"], captured.iframe_origins)
        self.assertEqual("Account Security", captured.from_display)
        self.assertEqual("security@example.test", captured.from_address)
        self.assertEqual("support@example.test", captured.reply_to)

    def test_stripe_capture_keeps_cdp_url_links_and_iframe_origins(self) -> None:
        captured = self.capture_cdp("stripe", {
            "text": "Card number CVC",
            "links": [["Terms", "https://stripe.com/legal"]],
            "iframes": ["https://js.stripe.com", "https://hooks.stripe.com"],
            "hasCardField": True,
        })

        self.assertEqual("https://merchant.example.test/checkout", captured.page_url)
        self.assertEqual("Card number CVC", captured.text)
        self.assertEqual([("Terms", "https://stripe.com/legal")], captured.links)
        self.assertEqual(
            ["https://js.stripe.com", "https://hooks.stripe.com"],
            captured.iframe_origins,
        )

    def test_crypto_address_extraction_requires_payment_context_and_boundaries(self) -> None:
        context = context_module()
        address = "0x1234567890abcdef1234567890abcdef12345678"
        transaction_hash = "0x" + "a" * 64

        def capture_text(text: str):
            with (
                patch.object(context, "_clipboard_text", return_value=""),
                patch.object(context, "_recent_downloads", return_value=[]),
                patch.object(context, "_cdp_targets", return_value=[]),
                patch.object(context, "_uia_context", return_value=(None, text)),
                patch.object(context, "_ocr_context", return_value=(None, ""), create=True),
            ):
                return context.capture("crypto")

        self.assertEqual(address, capture_text(f"Send ETH to {address}").displayed_address)
        self.assertIsNone(capture_text(f"Transaction id: {address}").displayed_address)
        self.assertIsNone(capture_text(f"Transaction hash: {transaction_hash}").displayed_address)


class ServerCaptureSafetyTests(unittest.TestCase):
    def test_empty_capture_returns_caution_not_safe(self) -> None:
        import server
        from signals import ScreenContext

        with patch.object(server, "_capture", return_value=ScreenContext(observed_fields=set())):
            card = server._scan("page")

        self.assertTrue(card.startswith("⚠️"), card)
        self.assertIn("couldn't inspect", card)


class ExplanationProviderTests(unittest.TestCase):
    def test_deepseek_key_selects_official_anthropic_endpoint(self) -> None:
        import explain

        dotenv = SimpleNamespace(dotenv_values=lambda _path: {})
        with (
            patch.dict(sys.modules, {"dotenv": dotenv}),
            patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}, clear=True),
        ):
            key, base_url, model = explain._load_model_config()

        self.assertEqual("test-key", key)
        self.assertEqual("https://api.deepseek.com/anthropic", base_url)
        self.assertEqual("deepseek-v4-flash", model)

