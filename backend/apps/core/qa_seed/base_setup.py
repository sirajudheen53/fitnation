"""Base QA setup: platform admin + default tenant/branch + base catalogs.

Ports the ``setup_local.py`` flow (admin superuser, "FitNation Test Gym"
tenant, Main Branch) plus the catalog management commands (food items,
permissions, tenant-1 exercises and marketplace products).
"""

from __future__ import annotations

from django.core.management import call_command

from apps.branches.models import Branch
from apps.tenants.models import Tenant, TenantSettings
from apps.users.models import User

from .common import PASSWORDS, ensure_password, ensure_active

ADMIN_EMAIL = "admin@fitnation.test"
DEFAULT_TENANT_NAME = "FitNation Test Gym"


def seed_base(skip_catalogs: bool = False, reset_passwords: bool = True, echo=print):
    """Create the platform admin, default tenant, branch and base catalogs.

    Args:
        skip_catalogs: Skip the food/exercise/permission/marketplace catalogs.
        reset_passwords: Align existing account passwords with documented values.
        echo: Progress sink (command stdout writer).

    Returns:
        Tuple of (default tenant, main branch).
    """
    tenant, _ = Tenant.objects.get_or_create(
        name=DEFAULT_TENANT_NAME,
        defaults={
            "legal_name": "FitNation Test Gym Pvt Ltd",
            "subscription_plan": "professional",
            "status": Tenant.Status.ACTIVE,
            "contact_email": ADMIN_EMAIL,
            "contact_phone": "+919999999999",
        },
    )
    ensure_active(tenant)
    TenantSettings.objects.get_or_create(tenant=tenant)

    branch, _ = Branch.objects.get_or_create(
        tenant=tenant,
        name="Main Branch",
        defaults={
            "branch_type": "main",
            "address_line1": "123 Fitness St",
            "city": "Mumbai",
            "state": "Maharashtra",
            "postal_code": "400001",
            "country": "India",
            "phone": "+919999999999",
            "email": "main@fitnation.test",
            "is_active": True,
        },
    )

    admin = User.objects.filter(email=ADMIN_EMAIL).first()
    if admin is None:
        admin = User.objects.create_superuser(
            email=ADMIN_EMAIL,
            password=PASSWORDS["admin"],
            first_name="Admin",
            last_name="User",
            tenant=tenant,
            role="platform_admin",
        )
        echo(f"  admin created: {admin.email}")
    else:
        echo(f"  admin exists: {admin.email}")
    admin.is_email_verified = True
    admin.save()
    ensure_password(admin, PASSWORDS["admin"], reset=reset_passwords)

    if not skip_catalogs:
        call_command("seed_food_items")
        call_command("seed_permissions")
        call_command("seed_exercises", tenant=tenant.id)
        call_command("seed_marketplace", tenant=tenant.id)
        echo("  catalogs: food items, permissions, exercises, marketplace")

    return tenant, branch