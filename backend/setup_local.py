"""Quick setup script: creates test tenant, superuser, and seeds exercises."""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from apps.tenants.models import Tenant
from apps.users.models import User
from apps.branches.models import Branch

# Create test tenant
tenant, created = Tenant.objects.get_or_create(
    name="FitNation Test Gym",
    defaults={
        "legal_name": "FitNation Test Gym Pvt Ltd",
        "subscription_plan": "professional",
        "status": "active",
        "contact_email": "admin@fitnation.test",
        "contact_phone": "+919999999999",
    },
)
print(f"Tenant: {tenant.name} ({'created' if created else 'already exists'})")

# Create superuser
if not User.objects.filter(email="admin@fitnation.test").exists():
    user = User.objects.create_superuser(
        email="admin@fitnation.test",
        password="F1tNati0n!",
        first_name="Admin",
        last_name="User",
        tenant=tenant,
        role="platform_admin",
    )
    print(f"Superuser: {user.email} (created)")
else:
    print("Superuser: admin@fitnation.test (already exists)")

# Create a branch
branch, created = Branch.objects.get_or_create(
    name="Main Branch",
    tenant=tenant,
    defaults={
        "branch_type": "main",
        "address_line1": "123 Fitness St",
        "city": "Mumbai",
        "state": "Maharashtra",
        "postal_code": "400001",
        "country": "India",
        "phone": "+919999999999",
        "is_active": True,
    },
)
print(f"Branch: {branch.name} ({'created' if created else 'already exists'})")

# Now seed exercises
from django.core.management import call_command
call_command("seed_exercises")
print("\n✅ Setup complete!")
print("   Login: admin@fitnation.test / F1tNati0n!")