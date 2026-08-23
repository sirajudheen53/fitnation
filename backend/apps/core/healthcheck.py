"""Health check endpoint for container orchestration."""

from django.core.cache import cache
from django.db import connection
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """Return the service health status.

    Checks database connectivity and cache connectivity. Returns 200 when both
    are healthy, otherwise 503 with details about the failing component.
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request: Request) -> Response:
        """Run health checks and return the aggregated status.

        Args:
            request: The incoming DRF request.

        Returns:
            A JSON response with the health status of DB and cache.
        """
        db_status = self._check_db()
        cache_status = self._check_cache()

        if db_status == "ok" and cache_status == "ok":
            return Response(
                {"status": "healthy", "db": db_status, "cache": cache_status},
                status=200,
            )
        return Response(
            {
                "status": "unhealthy",
                "db": db_status,
                "cache": cache_status,
            },
            status=503,
        )

    @staticmethod
    def _check_db() -> str:
        """Verify the database is reachable.

        Returns:
            ``ok`` on success, otherwise an error message.
        """
        try:
            connection.ensure_connection()
        except Exception as exc:
            return f"error: {exc}"
        return "ok"

    @staticmethod
    def _check_cache() -> str:
        """Verify the cache backend is reachable.

        Returns:
            ``ok`` on success, otherwise an error message.
        """
        try:
            cache.set("health_check", "ok", timeout=5)
            value = cache.get("health_check")
            if value != "ok":
                return "error: unexpected cache value"
        except Exception as exc:
            return f"error: {exc}"
        return "ok"


health_check = HealthCheckView.as_view()
