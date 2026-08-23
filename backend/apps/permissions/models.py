"""RBAC models for roles, permissions, and assignments."""

from django.db import models

from apps.tenants.models import Tenant


class Role(models.Model):
    """Defines a role within the system."""

    class CoreRole(models.TextChoices):
        """Core system roles."""

        PLATFORM_ADMIN = "platform_admin", "Platform Admin"
        GYM_OWNER = "gym_owner", "Gym Owner"
        MANAGER = "manager", "Manager"
        TRAINER = "trainer", "Trainer"
        DIETITIAN = "dietitian", "Dietitian"
        CUSTOMER = "customer", "Customer"

    code = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system_role = models.BooleanField(default=True)
    is_tenant_custom = models.BooleanField(default=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Role model metadata."""

        db_table = "roles"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                condition=models.Q(is_tenant_custom=True),
                name="uq_role_tenant_code_custom",
            ),
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(is_tenant_custom=False),
                name="uq_role_code_system",
            ),
        ]

    def __str__(self) -> str:
        """Return role label."""
        return self.name


class Permission(models.Model):
    """Defines a granular permission in the form ``app.action_resource``."""

    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    app_label = models.CharField(max_length=50)
    action = models.CharField(max_length=20)
    resource = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Permission model metadata."""

        db_table = "permissions"
        ordering = ["app_label", "resource", "action"]
        unique_together = ["app_label", "action", "resource"]

    def __str__(self) -> str:
        """Return permission label."""
        return self.name


class RolePermission(models.Model):
    """Maps permissions to roles."""

    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name="permission_roles",
    )
    is_granted = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """RolePermission model metadata."""

        db_table = "role_permissions"
        unique_together = ["role", "permission"]

    def __str__(self) -> str:
        """Return mapping label."""
        return f"{self.role.code}: {self.permission.code}"


class UserRoleAssignment(models.Model):
    """Assigns a custom role to a user, optionally scoped to a branch."""

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="role_assignments",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="user_assignments",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="role_assignments",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_roles",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        """UserRoleAssignment model metadata."""

        db_table = "user_role_assignments"
        ordering = ["-assigned_at"]
