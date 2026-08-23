"""Branch management models."""

import uuid

from django.db import models

from apps.tenants.models import TenantModelMixin


class Branch(TenantModelMixin):
    """A physical gym location belonging to a vendor (tenant)."""

    class BranchType(models.TextChoices):
        """Branch type options."""

        MAIN = "main", "Main"
        SUB = "sub", "Sub-branch"

    uuid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    name = models.CharField(max_length=200)
    branch_type = models.CharField(
        max_length=10,
        choices=BranchType.choices,
        default=BranchType.MAIN,
    )
    address_line1 = models.CharField(max_length=300)
    address_line2 = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="India")
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    opening_time = models.TimeField(default="05:00")
    closing_time = models.TimeField(default="23:00")
    operating_days = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    is_headquarters = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Branch model metadata."""

        db_table = "branches"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="uq_branch_tenant_name",
            ),
        ]

    def __str__(self) -> str:
        """Return branch label."""
        return f"{self.name} — {self.city}"


class BranchAmenity(models.Model):
    """Amenities/facilities available at a branch."""

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="amenities",
    )
    name = models.CharField(max_length=100)
    is_available = models.BooleanField(default=True)

    class Meta:
        """BranchAmenity model metadata."""

        db_table = "branch_amenities"
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "name"],
                name="uq_amenity_branch_name",
            ),
        ]

    def __str__(self) -> str:
        """Return amenity label."""
        return f"{self.name} @ {self.branch.name}"


class BranchImage(models.Model):
    """Images uploaded for a branch."""

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image_url = models.URLField()
    caption = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """BranchImage model metadata."""

        db_table = "branch_images"
        ordering = ["sort_order"]

    def __str__(self) -> str:
        """Return image label."""
        return f"Image {self.id} @ {self.branch.name}"


class BranchTrainerAssignment(models.Model):
    """Maps trainers to branches (M2M)."""

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="trainer_assignments",
    )
    trainer = models.ForeignKey(
        "users.Trainer",
        on_delete=models.CASCADE,
        related_name="branch_assignments",
    )
    is_primary = models.BooleanField(default=False)
    assigned_at = models.DateTimeField(auto_now_add=True)
    unassigned_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        """BranchTrainerAssignment model metadata."""

        db_table = "branch_trainer_assignments"
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "trainer"],
                name="uq_branch_trainer",
            ),
        ]

    def __str__(self) -> str:
        """Return assignment label."""
        return f"{self.trainer} @ {self.branch.name}"
