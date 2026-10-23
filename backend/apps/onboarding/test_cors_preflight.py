"""CORS preflight contract for the ERP web app (issue #61).

The onboarding wizard's ``POST /onboarding/member/`` sends a custom
``Idempotency-Key`` header (double-submit guard). A browser refuses to send
the actual request when the CORS preflight does not allow every header the
request carries — the call fails client-side and never reaches Django. The
preflight must therefore allow ``idempotency-key`` alongside the defaults.
"""

from django.test import TestCase

PREFLIGHT_URL = "/api/v1/onboarding/member/"
ERP_ORIGIN = "http://localhost:3000"


class OnboardingPreflightTests(TestCase):
    """``OPTIONS /onboarding/member/`` preflight allows the wizard's headers."""

    def options(self, request_headers: str):
        """Send a preflight for POST with the given request headers."""
        return self.client.options(
            PREFLIGHT_URL,
            HTTP_ORIGIN=ERP_ORIGIN,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS=request_headers,
        )

    def test_preflight_allows_idempotency_key(self) -> None:
        """The exact wizard preflight (auth + JSON + Idempotency-Key) passes."""
        response = self.options("authorization, content-type, idempotency-key")

        self.assertEqual(response.status_code, 200)
        allow_headers = response.headers.get("Access-Control-Allow-Headers", "")
        allowed = {header.strip().lower() for header in allow_headers.split(",")}
        self.assertIn("idempotency-key", allowed)
        self.assertIn("authorization", allowed)
        self.assertIn("content-type", allowed)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), ERP_ORIGIN)

    def test_preflight_response_is_cacheable_and_allows_post(self) -> None:
        """Browsers cache preflights — the cached reply must allow POST too."""
        response = self.options("idempotency-key")

        self.assertEqual(response.status_code, 200)
        self.assertIn("POST", response.headers.get("Access-Control-Allow-Methods", ""))
        self.assertTrue(int(response.headers.get("Access-Control-Max-Age", "0")) > 0)
