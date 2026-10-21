"""Push device-token registration for the customer mobile app (FBOS-011 §7.4).

The phone registers its FCM token on login and on token rotation, and
deletes it on logout. Tokens are upserted per token string; a caller only
ever sees its own rows.
"""

from typing import ClassVar

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.customers.models import Customer
from apps.notifications.models import DeviceToken
from apps.notifications.serializers import DeviceTokenSerializer
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication
from apps.users.models import User


class DeviceTokenViewSet(ModelViewSet):
    """Register / list / delete the current customer's push devices.

    Mounted at ``api/v1/notifications/device-tokens/``. Customers only —
    staff accounts have no member device to register.
    """

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember]
    serializer_class = DeviceTokenSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]
    lookup_field = "pk"

    def _customer(self) -> Customer | None:
        """The caller's customer profile in the request tenant (or None)."""
        if self.request.tenant is None:
            return None
        return Customer.objects.filter(tenant=self.request.tenant, user=self.request.user).first()

    def get_queryset(self) -> DeviceToken:
        """Only the caller's own device rows (never other users' tokens)."""
        return DeviceToken.objects.for_tenant(self.request.tenant).filter(user=self.request.user)

    def create(self, request: Request) -> Response:
        """Upsert a device token for the current customer (idempotent).

        Returns:
            ``201`` (first registration) or ``200`` (token re-registered —
            e.g. after a re-install) with the serialized row; ``403`` for
            non-customer callers without a member profile.
        """
        if request.user.role != User.Role.CUSTOMER:
            return Response({"detail": "Only customers register push devices."}, status=status.HTTP_403_FORBIDDEN)
        customer = self._customer()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token, created = DeviceToken.objects.update_or_create(
            token=serializer.validated_data["token"],
            defaults={
                "tenant": request.tenant,
                "customer": customer,
                "user": request.user,
                "device_id": serializer.validated_data.get("device_id", ""),
                "platform": serializer.validated_data.get("platform", DeviceToken.Platform.ANDROID),
                "device_type": serializer.validated_data.get("device_type", ""),
                "is_active": True,
            },
        )
        output = self.get_serializer(token)
        return Response(output.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def destroy(self, request: Request, pk: int) -> Response:
        """Delete one of the caller's device tokens (logout path)."""
        token = self.get_object()
        token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
