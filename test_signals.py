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


if __name__ == "__main__":
    unittest.main()
