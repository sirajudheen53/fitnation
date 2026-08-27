"""Tenant-aware token authentication backend."""

from typing import Any

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.users.auth import AuthToken


class TenantTokenAuthentication(BaseAuthentication):
    """DRF authentication backend that resolves user and tenant from a token header.

    Expects ``Authorization: Token <key>``.
    """

    keyword = "Token"

    def authenticate(self, request: Any) -> tuple[Any, Any] | None:
        """Authenticate a request using the token header.

        Args:
            request: The incoming DRF request.

        Returns:
            A ``(user, token)`` tuple on success, or ``None`` when no token header
            is present.

        Raises:
            AuthenticationFailed: If the token is invalid or expired.
        """
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith(self.keyword):
            return None

        token_key = auth_header[len(self.keyword) :].strip()
        try:
            token = AuthToken.objects.select_related("user", "tenant").get(key=token_key, is_active=True)
        except AuthToken.DoesNotExist as exc:
            raise AuthenticationFailed("Invalid or expired token") from exc

        if token.expires_at and token.expires_at < timezone.now():
            raise AuthenticationFailed("Token expired")

        token.last_used_at = timezone.now()
        token.save(update_fields=["last_used_at"])

        user = token.user
        user._tenant_from_token = token.tenant

        return user, token

    def authenticate_header(self, request: Any) -> str:  # noqa: ARG002
        """Return the expected authorization keyword for 401 responses.

        Args:
            request: The incoming DRF request.

        Returns:
            The ``Token`` keyword.
        """
        return self.keyword
