"""Health check endpoint for container orchestration.

P0 lesson (prod /api/health/ intermittent 500): every component check is
individually guarded, the view itself never raises, and failures are LOGGED
(so tracebacks reach stderr even when prod logging drops them). A failing
component reports a degraded 503 — it can never crash the endpoint.
"""

import logging

from django.core.cache import cache
from django.db import connection
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """Return the service health status.

    Checks database, cache and media-storage connectivity. Returns 200 when
    all components are healthy, otherwise 503 with per-component details.
    Component failures never crash the endpoint.
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request: Request) -> Response:
        """Run health checks and return the aggregated status.

        Args:
            request: The incoming DRF request.

        Returns:
            A JSON response with the health status of db, cache and storage.
            200 when everything reports ``ok``; 503 (degraded) otherwise.
            This endpoint never raises — a crashed check reports as a failed
            component instead of a 500.
        """
        checks: dict = {}
        for name, check in (
            ("db", self._check_db),
            ("cache", self._check_cache),
            ("storage", self._check_storage),
        ):
            try:
                checks[name] = check()
            except Exception as exc:
                logger.exception("health check %s crashed", name)
                checks[name] = f"error: {exc}"

        healthy = all(value == "ok" for value in checks.values())
        payload = {"status": "healthy" if healthy else "unhealthy", **checks}
        return Response(payload, status=200 if healthy else 503)

    @staticmethod
    def _check_db() -> str:
        """Verify the database accepts a round-trip query.

        Returns:
            ``ok`` on success, otherwise an error message.
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as exc:
            return f"error: {exc}"
        return "ok"

    @staticmethod
    def _check_cache() -> str:
        """Verify the cache backend accepts a write + read.

        Returns:
            ``ok`` on success, otherwise an error message.
        """
        try:
            cache.set("health_check", "ok", timeout=5)
            if cache.get("health_check") != "ok":
                return "error: unexpected cache value"
        except Exception as exc:
            return f"error: {exc}"
        return "ok"

    @staticmethod
    def _check_storage() -> str:
        """Verify the default media storage backend is usable.

        Returns:
            ``ok`` on success, otherwise an error message. A credential-light
            existence probe exercises backend init + bucket access (GCS on
            QA/prod) without transferring data — cold-instance storage-init
            failures surface here as a degraded component, never a 500.
        """
        try:
            from django.core.files.storage import default_storage

            default_storage.exists("health_check_probe")
        except Exception as exc:
            return f"error: {exc}"
        return "ok"


health_check = HealthCheckView.as_view()
