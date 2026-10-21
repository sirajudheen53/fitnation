"""Entitlement enforcement layered on top of RBAC (FBOS-011 §2.4).

:class:`EntitlementRequired` answers *may this human use the app right now*;
:class:`~apps.permissions.permissions.RolePermission` keeps answering *what may
this role do*. The two are separate so gym staff are never entangled with
member billing state (ADR-003 decision 1).
"""

from typing import Any

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.customers.models import Customer
from apps.memberships.selectors import EntitlementStatus, get_app_entitlement

READ_ONLY_CODE = "app_access_read_only"
REQUIRED_CODE = "app_access_required"


class EntitlementRequired(BasePermission):
    """Customer-content gate — attach AFTER RolePermission in permission_classes.

    Behaviour per request (the database, not the credential, is the source of
    truth — opaque tokens carry no entitlement claims):

    - Tenant rollout flag (``tenant.features["app_access"]``) off → allow
      everything: the feature does not exist for that tenant (§9.2), so ERP
      flows and old app builds are unaffected.
    - Non-customer roles → allow (staff use the ERP, not the customer app;
      their authorization is RolePermission's job alone).
    - Customers: ``active`` → allow; ``grace`` → safe methods only; anything
      else → deny. The 403 body always carries a ``code`` so the mobile Dio
      interceptor can flip local entitlement state and route to the gate
      without a round-trip.
    """

    message = "An active membership is required to use the app."

    def has_permission(self, request: Any, view: Any) -> bool:
        """Evaluate the caller's live entitlement against the request method.

        Args:
            request: The incoming DRF request.
            view: The view being accessed. May declare
                ``entitlement_exempt_actions: set[str]`` — viewset actions
                always allowed regardless of entitlement (used where profile
                and gated content share one viewset, e.g. the customer
                profile vs its ``progress-photos`` action — FBOS-011 §2.4).

        Returns:
            ``True`` when the request may proceed.

        Raises:
            PermissionDenied: With a ``code``-tagged body when the entitlement
                does not cover the requested method.
        """
        user = request.user
        if not (user and user.is_authenticated):
            return False
        tenant = getattr(request, "tenant", None) or user.tenant
        if tenant is None:
            return True
        if not ((tenant.features or {}).get("app_access")):
            return True  # rollout flag off — the gate does not exist here
        exempt_actions = getattr(view, "entitlement_exempt_actions", None)
        if exempt_actions and getattr(view, "action", None) in exempt_actions:
            return True
        if user.role != "customer":
            return True

        customer = Customer.objects.filter(tenant=tenant, user=user).only("id", "tenant").first()
        entitlement = get_app_entitlement(customer, tenant=tenant)

        if entitlement.status == EntitlementStatus.ACTIVE:
            return True
        if entitlement.status == EntitlementStatus.GRACE:
            if request.method in SAFE_METHODS:
                return True
            raise PermissionDenied(
                {
                    "detail": "Your membership has expired — access is read-only until "
                    f"{entitlement.grace_end_date.isoformat()}.",
                    "code": READ_ONLY_CODE,
                },
            )
        raise PermissionDenied(
            {"detail": self.message, "code": REQUIRED_CODE},
        )
