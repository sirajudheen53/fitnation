"""Management command to seed roles, permissions, and role-permission mappings."""

from django.core.management.base import BaseCommand

from apps.permissions.models import Permission, Role, RolePermission


class Command(BaseCommand):
    """Seed the RBAC tables from the canonical permission registry."""

    help = "Seeds roles, permissions, and role-permission mappings."

    def handle(self, *args: Any, **options: Any) -> None:
        """Execute the seeding process.

        Args:
            *args: Positional arguments passed by Django.
            **options: Keyword options passed by Django.
        """
        self._seed_roles()
        self._seed_permissions()
        self._seed_role_permissions()
        self.stdout.write(self.style.SUCCESS("Permissions seeded successfully."))

    def _seed_roles(self) -> None:
        """Create the six core system roles."""
        for code, name in Role.CoreRole.choices:
            Role.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "is_system_role": True,
                    "is_tenant_custom": False,
                },
            )

    def _seed_permissions(self) -> None:
        """Create the canonical permission registry."""
        permission_registry = [
            ("tenants", "view", "tenant", "View tenant"),
            ("tenants", "edit", "tenant", "Edit tenant settings"),
            ("branches", "view", "branch", "View branches"),
            ("branches", "create", "branch", "Create branch"),
            ("branches", "edit", "branch", "Edit branch"),
            ("branches", "delete", "branch", "Delete/deactivate branch"),
            ("customers", "view", "customer", "View customers"),
            ("customers", "create", "customer", "Create customer"),
            ("customers", "edit", "customer", "Edit customer"),
            ("customers", "delete", "customer", "Delete customer"),
            ("users", "view", "user", "View users"),
            ("users", "create", "user", "Create user"),
            ("users", "edit", "user", "Edit user"),
            ("users", "delete", "user", "Deactivate user"),
            ("memberships", "view", "membership", "View memberships"),
            ("memberships", "create", "membership", "Create membership"),
            ("memberships", "edit", "membership", "Edit membership"),
            ("payments", "view", "payment", "View payments"),
            ("payments", "record", "payment", "Record payment"),
            ("attendance", "view", "attendance", "View attendance"),
            ("attendance", "log", "attendance", "Log attendance"),
            ("workouts", "view", "workout", "View workout plans"),
            ("workouts", "create", "workout", "Create workout plan"),
            ("workouts", "edit", "workout", "Edit workout plan"),
            ("diets", "view", "diet", "View diet plans"),
            ("diets", "create", "diet", "Create diet plan"),
            ("diets", "edit", "diet", "Edit diet plan"),
            ("reports", "view", "report", "View reports"),
            ("dashboard", "view", "dashboard", "View dashboard"),
            ("marketplace", "view", "product", "View marketplace products"),
            ("marketplace", "edit", "product", "Edit marketplace products"),
            ("marketplace", "delete", "product", "Delete marketplace products"),
            ("marketplace", "view", "cart", "View shopping cart"),
            ("marketplace", "edit", "cart", "Edit shopping cart"),
            ("marketplace", "view", "order", "View orders"),
            ("marketplace", "create", "order", "Place orders"),
            ("marketplace", "edit", "order", "Edit orders"),
            ("marketplace", "delete", "order", "Delete orders"),
        ]

        for app_label, action, resource, name in permission_registry:
            code = f"{app_label}.{action}_{resource}"
            Permission.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "app_label": app_label,
                    "action": action,
                    "resource": resource,
                },
            )

    def _seed_role_permissions(self) -> None:
        """Map permissions to roles per the canonical matrix."""
        role_matrix: dict[str, list[str] | str] = {
            "platform_admin": "*",
            "gym_owner": "*",
            "manager": [
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
                "marketplace.view_product",
                "marketplace.edit_product",
                "marketplace.delete_product",
                "marketplace.view_cart",
                "marketplace.edit_cart",
                "marketplace.view_order",
                "marketplace.create_order",
                "marketplace.edit_order",
                "marketplace.delete_order",
            ],
            "trainer": [
                "customers.view_customer",
                "memberships.view_membership",
                "attendance.view_attendance",
                "attendance.log_attendance",
                "workouts.view_workout",
                "workouts.create_workout",
                "workouts.edit_workout",
                "dashboard.view_dashboard",
            ],
            "dietitian": [
                "customers.view_customer",
                "diets.view_diet",
                "diets.create_diet",
                "diets.edit_diet",
                "marketplace.view_product",
            ],
            "customer": [
                "memberships.view_membership",
                "payments.view_payment",
                "attendance.view_attendance",
                "attendance.log_attendance",
                "workouts.view_workout",
                "diets.view_diet",
                "marketplace.view_product",
                "marketplace.view_cart",
                "marketplace.edit_cart",
                "marketplace.view_order",
                "marketplace.create_order",
            ],
        }

        for role_code, perm_codes in role_matrix.items():
            role = Role.objects.get(code=role_code)
            if perm_codes == "*":
                for perm in Permission.objects.all():
                    RolePermission.objects.get_or_create(
                        role=role,
                        permission=perm,
                        defaults={"is_granted": True},
                    )
            else:
                for code in perm_codes:
                    try:
                        perm = Permission.objects.get(code=code)
                    except Permission.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(f"Permission not found: {code}")
                        )
                        continue
                    RolePermission.objects.get_or_create(
                        role=role,
                        permission=perm,
                        defaults={"is_granted": True},
                    )
