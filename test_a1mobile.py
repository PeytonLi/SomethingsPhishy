import os
import unittest
from unittest.mock import Mock, patch

import requests

from a1mobile import normalize_guardian_phone, place_guardian_call


class NormalizeGuardianPhoneTests(unittest.TestCase):
    def test_normalizes_us_ten_digit_number(self):
        self.assertEqual(normalize_guardian_phone("(415) 555-2671"), "+14155552671")

    def test_rejects_invalid_number(self):
        with self.assertRaises(ValueError):
            normalize_guardian_phone("12345")


class PlaceGuardianCallTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    @patch("a1mobile.requests.post")
    def test_missing_configuration_is_safe(self, post):
        result = place_guardian_call()

        self.assertFalse(result.placed)
        self.assertIn("not configured", result.message)
        post.assert_not_called()

    @patch.dict(
        os.environ,
        {
            "A1MOBILE_TEAM_KEY": "secret-team-key",
            "A1MOBILE_GUARDIAN_PHONE": "415-555-2671",
            "A1MOBILE_BASE_URL": "https://example.test/",
        },
        clear=True,
    )
    @patch("a1mobile.requests.post")
    def test_success_posts_normalized_number(self, post):
        post.return_value = Mock(status_code=201)

        result = place_guardian_call(timeout=3)

        self.assertTrue(result.placed)
        post.assert_called_once_with(
            "https://example.test/api/calls",
            headers={"X-Team-Key": "secret-team-key"},
            json={"to": "+14155552671"},
            timeout=3,
        )

    @patch.dict(
        os.environ,
        {
            "A1MOBILE_TEAM_KEY": "secret-team-key",
            "A1MOBILE_GUARDIAN_PHONE": "4155552671",
        },
        clear=True,
    )
    @patch("a1mobile.requests.post")
    def test_api_rejection_reports_unverified_safely(self, post):
        response = Mock(status_code=400)
        response.json.return_value = {"error": "Phone number is unverified"}
        post.return_value = response

        result = place_guardian_call()

        self.assertFalse(result.placed)
        self.assertIn("not verified", result.message)
        self.assertNotIn("secret-team-key", result.message)

    @patch.dict(
        os.environ,
        {
            "A1MOBILE_TEAM_KEY": "secret-team-key",
            "A1MOBILE_GUARDIAN_PHONE": "4155552671",
        },
        clear=True,
    )
    @patch("a1mobile.requests.post", side_effect=requests.Timeout)
    def test_network_error_returns_safe_result(self, _post):
        result = place_guardian_call()

        self.assertFalse(result.placed)
        self.assertIn("unavailable", result.message)


if __name__ == "__main__":
    unittest.main()
