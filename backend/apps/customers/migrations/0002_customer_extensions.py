# Generated for FBOS-003: Customer Management extensions

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("branches", "0002_initial"),
        ("tenants", "0001_initial"),
        ("users", "0003_remove_membership_customer_remove_membership_plan_and_more"),
        ("customers", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add new fields to Customer
        migrations.AddField(
            model_name="customer",
            name="address_street",
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name="customer",
            name="address_city",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="customer",
            name="address_state",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="customer",
            name="address_postal_code",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="customer",
            name="profile_photo",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="customer-photos/",
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("inactive", "Inactive"),
                    ("suspended", "Suspended"),
                ],
                default="active",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="notes",
            field=models.TextField(blank=True),
        ),
        # Add new JSON fields to HealthProfile
        migrations.AddField(
            model_name="healthprofile",
            name="medical_conditions",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="healthprofile",
            name="allergies",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="healthprofile",
            name="medications",
            field=models.JSONField(blank=True, default=list),
        ),
        # Create ProgressPhoto model
        migrations.CreateModel(
            name="ProgressPhoto",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "image",
                    models.ImageField(upload_to="progress-photos/"),
                ),
                ("caption", models.CharField(blank=True, max_length=300)),
                ("taken_at", models.DateTimeField(auto_now_add=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progress_photos",
                        to="customers.customer",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "progress_photos",
                "ordering": ["-taken_at", "-created_at"],
            },
        ),
    ]