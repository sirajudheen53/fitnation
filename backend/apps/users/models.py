"""Custom tenant-aware user model and related profiles."""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from apps.tenants.models import Tenant


class UserManager(BaseUserManager):
    """Custom user manager that identifies users by email."""

    use_in_migrations = True

    def _create_user(
        self,
        email: str,
        password: str,
        **extra_fields: object,
    ) -> "User":
        """Create and save a user with the given email and password."""
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def for_tenant(self, tenant: "Tenant") -> "models.QuerySet[User]":
        """Return a queryset filtered to the supplied tenant.

        Args:
            tenant: The tenant instance to filter by.

        Returns:
            Queryset containing only users belonging to the given tenant.
        """
        return self.get_queryset().filter(tenant=tenant)

    def create_user(
        self,
        email: str,
        password: str = "",
        **extra_fields: object,
    ) -> "User":
        """Create a regular user."""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(
        self,
        email: str,
        password: str = "",
        **extra_fields: object,
    ) -> "User":
        """Create a platform admin superuser."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "platform_admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Tenant-aware user. Platform admins have ``tenant_id=NULL``."""

    class Role(models.TextChoices):
        """Core user roles."""

        PLATFORM_ADMIN = "platform_admin", "Platform Admin"
        GYM_OWNER = "gym_owner", "Gym Owner"
        MANAGER = "manager", "Manager"
        TRAINER = "trainer", "Trainer"
        DIETITIAN = "dietitian", "Dietitian"
        CUSTOMER = "customer", "Customer"

    username = None
    email = models.EmailField(unique=True)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
        db_index=True,
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
    )
    phone = models.CharField(max_length=20, blank=True)
    is_owner = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        """User model metadata."""

        db_table = "users"

    def __str__(self) -> str:
        """Return user label."""
        return f"{self.email} ({self.role})"


class Trainer(models.Model):
    """Trainer profile linked one-to-one to a user."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="trainer_profile",
    )
    specialization = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Trainer model metadata."""

        db_table = "trainers"

    def __str__(self) -> str:
        """Return trainer label."""
        return f"Trainer: {self.user.email}"


class AuthToken(models.Model):
    """Extended token model with tenant context and device info."""

    class DeviceType(models.TextChoices):
        """Known device types."""

        WEB = "web", "Web"
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"

    key = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="auth_tokens",
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="auth_tokens",
    )
    device_id = models.CharField(max_length=200, blank=True)
    device_type = models.CharField(
        max_length=20,
        blank=True,
        choices=DeviceType.choices,
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """AuthToken model metadata."""

        db_table = "auth_tokens"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return token label."""
        return f"{self.user.email} — {self.device_type or 'web'}"

    def save(self, *args: object, **kwargs: object) -> None:
        """Generate a key automatically when missing."""
        if not self.key:
            self.key = self.generate_key()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_key() -> str:
        """Generate a 64-character random token key."""
        import uuid

        return uuid.uuid4().hex + uuid.uuid4().hex


