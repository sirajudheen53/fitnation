"""Tests for the core app shared utilities."""

from rest_framework.test import APITestCase


class HealthCheckTests(APITestCase):
    """Tests for the liveness/readiness health endpoint."""

    def test_health_endpoint_returns_healthy(self) -> None:
        """The health endpoint reports database and cache status."""
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "healthy")
        self.assertEqual(response.data["db"], "ok")
