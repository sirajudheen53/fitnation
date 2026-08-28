"""DRF permission classes for role-based access control."""

from typing import Any

from rest_framework.permissions import BasePermission, IsAuthenticated


class IsPlatformAdmin(BasePermission):
    """Only platform admins (superusers)."""

    def has_permission(self, request: Any, view: Any) -> bool:
        """Check for platform admin role.

        Args:
            request: The incoming DRF request.
            view: The view being accessed.

        Returns:
            ``True`` if the user is authenticated and a superuser.
        """
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)


class RolePermission(BasePermission):
    """Permission class that checks a required permission against the user's role.

    Views declare the required permission via ``required_permission`` class attribute.
    Platform admins and gym owners are granted all tenant-scoped permissions.
    """

    ROLE_PERMISSION_MATRIX: dict[str, set[str] | str] = {
        "platform_admin": "*",
        "gym_owner": "*",
        "manager": {
            "branches.view_branch",
            "customers.view_customer",
            "customers.create_customer",
            "customers.edit_customer",
            "users.view_user",
            "users.create_user",
            "users.edit_user",
            "memberships.view_membership",
            "memberships.create_membership",
            "memberships.edit_membership",
            "payments.view_payment",
            "payments.record_payment",
            "attendance.view_attendance",
            "attendance.log_attendance",
            "dashboard.view_dashboard",
            "reports.view_report",
            "feedback.view_feedback",
            "feedback.create_feedback",
            "feedback.edit_feedback",
            "exercises.view_exercise",
            "exercises.edit_exercise",
            "exercises.delete_exercise",
            "marketplace.view_product",
            "marketplace.edit_product",
            "marketplace.delete_product",
            "marketplace.view_cart",
            "marketplace.edit_cart",
            "marketplace.view_order",
            "marketplace.create_order",
            "marketplace.edit_order",
            "marketplace.delete_order",
            "inventory.view_equipment",
            "inventory.create_equipment",
            "inventory.edit_equipment",
            "inventory.delete_equipment",
            "inventory.view_inventory",
            "inventory.create_inventory",
            "inventory.edit_inventory",
            "inventory.delete_inventory",
            "reviews.view_review",
            "reviews.edit_review",
        },
        "trainer": {
            "customers.view_customer",
            "memberships.view_membership",
            "attendance.view_attendance",
            "attendance.log_attendance",
            "workouts.view_workout",
            "workouts.create_workout",
            "workouts.edit_workout",
            "dashboard.view_dashboard",
            "feedback.view_feedback",
            "feedback.edit_feedback",
            "exercises.view_exercise",
            "exercises.edit_exercise",
            "exercises.delete_exercise",
            "reviews.view_review",
            "reviews.edit_review",
        },
        "dietitian": {
            "customers.view_customer",
            "diets.view_diet",
            "diets.create_diet",
            "diets.edit_diet",
            "ai_nutrition.view",
            "ai_nutrition.create",
            "ai_nutrition.edit",
            "marketplace.view_product",
        },
        "customer": {
            "memberships.view_membership",
            "payments.view_payment",
            "attendance.view_attendance",
            "attendance.log_attendance",
            "workouts.view_workout",
            "diets.view_diet",
            "ai_nutrition.view",
            "feedback.view_feedback",
            "feedback.create_feedback",
            "exercises.view_exercise",
            "customers.view_customer",
            "customers.view_healthprofile",
            "customers.view_fitnessgoal",
            "customers.view_bodymeasurement",
            "marketplace.view_product",
            "marketplace.view_cart",
            "marketplace.edit_cart",
            "marketplace.view_order",
            "marketplace.create_order",
            "reviews.view_review",
            "reviews.create_review",
        },
    }

    METHOD_PERMISSIONS: dict[str, str] = {}

    def has_permission(self, request: Any, view: Any) -> bool:
        """Evaluate whether the user's role grants the required permission.

        Args:
            request: The incoming DRF request.
            view: The view being accessed.

        Returns:
            ``True`` if the user is authorized for the required permission.
        """
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        # Check method-specific permission first, fall back to class default
        method = getattr(request, "method", None)
        required = None
        if method is not None:
            required = getattr(view, "method_permissions", {}).get(method)
        if required is None:
            required = getattr(view, "required_permission", None)
        if required is None:
            return True

        allowed = self.ROLE_PERMISSION_MATRIX.get(request.user.role, set())
        if allowed == "*":
            return True

        return required in allowed

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        """Object-level authorization check.

        Ensures the object belongs to the user's tenant. Customers can only access
        their own records.

        Args:
            request: The incoming DRF request.
            view: The view being accessed.
            obj: The model instance being accessed.

        Returns:
            ``True`` if the object is accessible to the requesting user.
        """
        if not request.user.is_authenticated or request.user.is_superuser:
            return True

        if hasattr(obj, "tenant_id") and obj.tenant_id is not None:
            if obj.tenant_id != request.user.tenant_id:
                return False

        if request.user.role == "customer":
            if hasattr(obj, "user_id") and obj.user_id == request.user.id:
                return True
            if hasattr(obj, "customer_id"):
                from apps.users.models import User

                try:
                    customer_user_id = getattr(
                        obj,
                        "customer_user_id",
                        User.objects.get(
                            customer_profile__id=obj.customer_id,
                        ).id,
                    )
                except User.DoesNotExist:
                    return False
                return customer_user_id == request.user.id
            return False

        return True


class RolePermissionMixin:
    """Convenience mixin for class-based views that sets permission classes.

    Subclasses must set ``required_permission``.
    """

    required_permission: str | None = None
    authentication_classes = ["apps.users.authentication.TenantTokenAuthentication"]
    permission_classes = [
        IsAuthenticated,
        "apps.tenants.permissions.IsTenantMember",
        RolePermission,
    ]
