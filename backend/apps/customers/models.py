"""Customer management models."""

from django.db import models

from apps.branches.models import Branch
from apps.tenants.models import TenantModelMixin
from apps.users.models import User


class Customer(TenantModelMixin):
    """A tenant-scoped customer profile linked one-to-one to a user."""

    class Gender(models.TextChoices):
        """Gender options for a customer."""

        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"
        PREFER_NOT_TO_SAY = "prefer_not_to_say", "Prefer not to say"

    class Status(models.TextChoices):
        """Lifecycle status of a customer."""

        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        SUSPENDED = "suspended", "Suspended"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers",
    )
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20,
        choices=Gender.choices,
        default=Gender.PREFER_NOT_TO_SAY,
    )
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    address_street = models.CharField(max_length=300, blank=True)
    address_city = models.CharField(max_length=100, blank=True)
    address_state = models.CharField(max_length=100, blank=True)
    address_postal_code = models.CharField(max_length=20, blank=True)
    profile_photo = models.ImageField(
        upload_to="customer-photos/",
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Customer model metadata."""

        db_table = "customers"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "email"],
                name="uq_customer_tenant_email",
            ),
        ]

    def __str__(self) -> str:
        """Return customer label."""
        return f"Customer: {self.name}"


class HealthProfile(TenantModelMixin):
    """Health-related profile for a customer."""

    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name="health_profile",
    )
    height_cm = models.DecimalField(max_digits=5, decimal_places=2)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2)
    bmi = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    injuries = models.TextField(blank=True)
    medical_info = models.JSONField(default=dict, blank=True)
    medical_conditions = models.JSONField(default=list, blank=True)
    allergies = models.JSONField(default=list, blank=True)
    medications = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """HealthProfile model metadata."""

        db_table = "health_profiles"

    def save(self, *args: object, **kwargs: object) -> None:
        """Persist and auto-calculate BMI when height and weight are present."""
        if self.height_cm and self.weight_kg:
            try:
                height_m = float(self.height_cm) / 100
                weight_kg = float(self.weight_kg)
                self.bmi = round(weight_kg / (height_m * height_m), 2)
            except (TypeError, ValueError):
                self.bmi = None
        else:
            self.bmi = None
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """Return health profile label."""
        return f"HealthProfile: {self.customer.name}"


class FitnessGoal(TenantModelMixin):
    """Fitness goals declared by a customer."""

    class GoalType(models.TextChoices):
        """Supported fitness goal types."""

        LOSE_WEIGHT = "lose_weight", "Lose Weight"
        BUILD_MUSCLE = "build_muscle", "Build Muscle"
        ENDURANCE = "endurance", "Endurance"
        FLEXIBILITY = "flexibility", "Flexibility"
        GENERAL_FITNESS = "general_fitness", "General Fitness"
        OTHER = "other", "Other"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="fitness_goals",
    )
    goal_type = models.CharField(
        max_length=50,
        choices=GoalType.choices,
        default=GoalType.GENERAL_FITNESS,
    )
    is_active = models.BooleanField(default=True)
    target_value = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """FitnessGoal model metadata."""

        db_table = "fitness_goals"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return fitness goal label."""
        return f"{self.customer.name} — {self.goal_type}"


class BodyMeasurement(TenantModelMixin):
    """Customer body measurements logged over time."""

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="body_measurements",
    )
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2)
    chest_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    waist_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    hips_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    arms_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    legs_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    date_logged = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """BodyMeasurement model metadata."""

        db_table = "body_measurements"
        ordering = ["-date_logged", "-created_at"]

    def __str__(self) -> str:
        """Return measurement label."""
        return f"Measurement: {self.customer.name} @ {self.date_logged}"


class ProgressPhoto(TenantModelMixin):
    """Progress photos logged by a customer over time."""

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="progress_photos",
    )
    image = models.ImageField(upload_to="progress-photos/")
    caption = models.CharField(max_length=300, blank=True)
    taken_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """ProgressPhoto model metadata."""

        db_table = "progress_photos"
        ordering = ["-taken_at", "-created_at"]

    def __str__(self) -> str:
        """Return progress photo label."""
        return f"ProgressPhoto: {self.customer.name} @ {self.taken_at}"
