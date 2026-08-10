from __future__ import annotations

import builtins
import importlib
import importlib.util
import os
import sys
import time
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

    def test_unique_visible_cdp_tab_is_selected_when_voice_os_is_foreground(self) -> None:
        context = context_module()
        logitech = page_target("Checkout", "https://www.logitechg.com/en-us/checkout")
        elevenlabs = page_target("Subscription | ElevenLabs", "https://elevenlabs.io/app/subscription/creative")

        with (
            patch.object(context, "_foreground_title", return_value="VoiceOS"),
            patch.object(
                context,
                "_cdp_visibility",
                side_effect=lambda target: "visible" if target is logitech else "hidden",
                create=True,
            ),
        ):
            selected = context._pick_target([logitech, elevenlabs])

        self.assertIs(logitech, selected)

    def test_uia_browser_text_excludes_inactive_tab_names(self) -> None:
        context = context_module()
        url = "https://www.logitechg.com/en-us/checkout"
        tab = SimpleNamespace(
            Name="PhishScope — Security Scenario Lab",
            ControlTypeName="TabItemControl",
        )
        address = SimpleNamespace(
            Name="Address and search bar",
            ControlTypeName="EditControl",
            GetValuePattern=lambda: SimpleNamespace(Value=url),
        )
        cart = SimpleNamespace(Name="Shopping cart", ControlTypeName="TextControl")
        total = SimpleNamespace(Name="Order total", ControlTypeName="TextControl")
        document = SimpleNamespace(
            Name="Checkout | Logitech G",
            ControlTypeName="DocumentControl",
            GetDescendants=lambda maxDepth=8: [cart, total],
        )
        root = SimpleNamespace(
            GetDescendants=lambda maxDepth=8: [tab, address, document, cart, total],
        )
        auto = SimpleNamespace(GetForegroundControl=lambda: root)

        with patch.dict(sys.modules, {"uiautomation": auto}):
            page_url, text = context._uia_context()

        self.assertEqual(url, page_url)
        self.assertIn("Shopping cart", text)
        self.assertNotIn("PhishScope", text)

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

    def test_empty_canvas_dom_uses_ocr_despite_browser_chrome_text(self) -> None:
        context = context_module()
        target = page_target("OCR Demo", "http://127.0.0.1:8080/ocr.html")
        with (
            patch.object(context, "_clipboard_text", return_value=""),
            patch.object(context, "_foreground_title", return_value="OCR Demo - Chrome"),
            patch.object(context, "_cdp_targets", return_value=[target]),
            patch.object(context, "_cdp_dom", return_value={"text": "", "links": [], "iframes": []}),
            patch.object(context, "_uia_context", return_value=(target["url"], "Address and search bar")),
            patch.object(context, "_ocr_context", return_value=(None, "Your computer is infected. Do not shut down")),
        ):
            captured = context.capture("page")

        self.assertIn("computer is infected", captured.text)
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
    def test_safe_scan_skips_explanation_and_bounds_slow_enrichment(self) -> None:
        import server
        from signals import ScreenContext

        context = ScreenContext(
            text="Sign in with Google",
            page_url="https://accounts.google.com/",
            observed_fields={"text", "page_url", "links", "iframe_origins"},
        )
        humanize = Mock(side_effect=AssertionError("SAFE scan must not call a model"))

        def slow_enrich(_domain: str, _timeout: float) -> dict[str, Any]:
            time.sleep(2)
            return {}

        started = time.monotonic()
        with (
            patch.object(server, "_capture", return_value=context),
            patch.object(server, "_enrich", new=slow_enrich),
            patch.object(server, "_humanize", humanize),
        ):
            card = server._scan("page")
        elapsed = time.monotonic() - started

        self.assertTrue(card.startswith("**SAFE — This page looks okay**"), card)
        self.assertNotIn("✅", card)
        self.assertNotIn("→", card)
        self.assertLess(elapsed, 1.0)
        humanize.assert_not_called()

    def test_voice_tool_marks_card_verbatim_without_removing_bullets(self) -> None:
        import server

        card = "**SAFE — This page looks okay**\n\n• **First reason**\n  Details\n\n• **Second reason**\n  Details"
        with patch.object(server, "_scan", return_value=card):
            response = server.check_this_page()

        self.assertIn("Relay the safety card below verbatim", response)
        self.assertIn("• **First reason**", response)
        self.assertIn("• **Second reason**", response)
        self.assertNotIn("→", response)
        self.assertTrue(response.endswith("  Details"))

    def test_safe_checkout_card_explains_positive_evidence(self) -> None:
        import server
        from signals import ScreenContext

        context = ScreenContext(
            text="Express checkout Apple Pay PayPal Card number CVC",
            page_url="https://www.logitechg.com/en-us/checkout",
            links=[("Terms", "https://www.logitechg.com/en-us/terms")],
            iframe_origins=["https://js.stripe.com"],
            observed_fields={"text", "page_url", "links", "iframe_origins"},
        )
        with (
            patch.object(server, "_capture", return_value=context),
            patch.object(server, "_enrich", return_value={}),
        ):
            card = server._scan("page")

        self.assertTrue(card.startswith("**SAFE — This page looks okay**"), card)
        self.assertNotIn("✅", card)
        self.assertNotIn("→", card)
        self.assertIn("**Website address**", card)
        self.assertIn("logitechg.com", card)
        self.assertIn("**Payment form**", card)
        self.assertIn("Stripe", card)
        self.assertIn("**Payment choices**", card)
        self.assertGreaterEqual(card.count("•"), 3)

    def test_empty_capture_returns_caution_not_safe(self) -> None:
        import server
        from signals import ScreenContext

        with patch.object(server, "_capture", return_value=ScreenContext(observed_fields=set())):
            card = server._scan("page")

        self.assertTrue(card.startswith("**CAUTION — Pause before using this page**"), card)
        self.assertNotIn("⚠️", card)
        self.assertNotIn("→", card)
        self.assertIn("couldn't inspect", card)

    def test_danger_card_starts_with_an_explicit_status(self) -> None:
        import server

        card = server.render_verdict_card({
            "verdict": "DANGER",
            "findings": [{
                "title": "The address imitates a trusted site",
                "evidence": "The displayed address does not match the real domain.",
            }],
            "action": "Close this page.",
        })

        self.assertTrue(card.startswith("**DANGER — Do not continue**"), card)
        self.assertNotIn("✅", card)
        self.assertNotIn("→", card)
        self.assertIn("**What to do**", card)


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

