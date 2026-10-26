"""Customer management serializers."""

from typing import ClassVar

from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.fields import SerializerMethodField

from PIL import Image

from apps.customers.models import (
    DELETED_USER_LABEL,
    BodyMeasurement,
    Customer,
    FitnessGoal,
    HealthProfile,
    ProgressPhoto,
)
from apps.users.models import User
from apps.users.services import SYNTHETIC_EMAIL_DOMAIN, synthetic_otp_email

# FBOS-026 part 1: profile photo constraints (JPEG/PNG/WebP, max 5 MB).
ALLOWED_PROFILE_PHOTO_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_PROFILE_PHOTO_BYTES = 5 * 1024 * 1024


class DeletedCustomerFlagMixin(serializers.Serializer):
    """Expose the soft-delete state of a row's customer (issue #81).

    Any surface serializer whose rows reference a customer mixes this in so
    the payload carries ``customer_is_deleted`` — the frontend badges the
    reference instead of pattern-matching the display name. The referenced
    customer renders as :data:`DELETED_USER_LABEL` regardless: the delete
    scrubs the stored name, and :meth:`CustomerSerializer.to_representation`
    would force it anyway. (Subclasses ``serializers.Serializer`` so the
    declared field is collected into ``_declared_fields`` — a plain mixin's
    class attributes are invisible to DRF's metaclass.)
    """

    customer_is_deleted = serializers.SerializerMethodField()

    def get_customer_is_deleted(self, obj) -> bool:
        """True when the row points at a soft-deleted customer."""
        customer = getattr(obj, "customer", None)
        return customer is not None and customer.deleted_at is not None


class CustomerSerializer(serializers.ModelSerializer):
    """Serialize customer details.

    Create contract (ADR customer-creation blessing): the payload carries
    ``first_name``/``last_name``/``email`` (+ ``branch``); the linked
    customer-role portal User is auto-provisioned from the email (unusable
    password — customers log in via OTP; ``is_email_verified=True`` since the
    owner vouches for the address). ``name``/``user``/``branch`` remain
    writable for mobile/tests.

    Email is optional (msg 2438): a phone-only customer gets a portal user
    under the tenant-scoped synthetic OTP email
    ``{phone}.{tenant_uuid}@fitnation.local`` while ``Customer.email`` stays
    NULL, and adding a real email later adopts it onto the same user
    (ADR-002 convergence).
    """

    first_name = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=150)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    name = serializers.CharField(max_length=200, required=False)
    app_invite_status = SerializerMethodField()
    # Issue #81: read-only soft-delete marker (never writable via the API).
    is_deleted = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata."""

        model = Customer
        fields: ClassVar[list[str]] = [
            "id",
            "user",
            "branch",
            "name",
            "first_name",
            "last_name",
            "email",
            "phone",
            "date_of_birth",
            "gender",
            "emergency_contact_name",
            "emergency_contact_phone",
            "address_street",
            "address_city",
            "address_state",
            "address_postal_code",
            "profile_photo",
            "status",
            "notes",
            "is_active",
            "is_deleted",
            "app_invite_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "created_at", "updated_at"]

    def get_is_deleted(self, obj: Customer) -> bool:
        """Return the soft-delete marker (issue #81)."""
        return obj.deleted_at is not None

    def to_representation(self, instance: Customer) -> dict:
        """Force the deleted-customer display label on every payload.

        The ERP delete scrubs ``name`` to the label already; this guards the
        GDPR-anonymized rows (stored "Deleted member #pk") and any future
        path that leaves a personal name on a marked row — a deleted
        customer's name never leaves the backend (issue #81).
        """
        data = super().to_representation(instance)
        if instance.deleted_at is not None:
            data["name"] = DELETED_USER_LABEL
        return data

    def get_app_invite_status(self, obj: Customer) -> dict | None:
        """Summarize the latest ``app_invite`` notification for the member.

        Consumed by the customer-detail card and the onboarding wizard's
        returning-member path (FBOS-011 §5.1b).

        Args:
            obj: The customer.

        Returns:
            ``{"status", "channel", "sent_at", "error_message"}`` for the most
            recent invite log, or ``None`` when the member was never invited.
        """
        log = (
            obj.notification_logs.filter(notification_type="app_invite")
            .select_related("customer")
            .order_by("-created_at")
            .first()
        )
        if log is None:
            return None
        return {
            "status": log.status,
            "channel": log.channel or None,
            "sent_at": log.created_at,
            "error_message": log.error_message or None,
        }

    def validate_profile_photo(self, value):
        """FBOS-026: accept JPEG/PNG/WebP only, max 5 MB."""
        if not value:
            return value
        if value.size > MAX_PROFILE_PHOTO_BYTES:
            raise serializers.ValidationError("Profile photo must be 5 MB or smaller.")
        fmt = None
        try:
            with Image.open(value) as image:
                fmt = image.format
                image.verify()
        except Exception:  # noqa: BLE001 — any parse failure means invalid image
            raise serializers.ValidationError("Profile photo must be a valid JPEG, PNG or WebP image.") from None
        finally:
            if hasattr(value, "seek"):
                value.seek(0)
        if fmt not in ALLOWED_PROFILE_PHOTO_FORMATS:
            raise serializers.ValidationError("Profile photo must be a JPEG, PNG or WebP image.")
        return value

    def validate(self, data: dict) -> dict:
        """Ensure a tenant does not contain duplicate customer emails.

        Email is optional (msg 2438): an empty string normalizes to None and
        skips the duplicate check, and a create with neither email nor phone
        is rejected. Name composition (ADR customer-creation blessing): when
        either ``first_name`` or ``last_name`` is present, the whitespace-
        collapsed ``"{first} {last}".strip()`` composition wins over a
        provided ``name``.
        """
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        if "email" in data:
            data["email"] = (data.get("email") or "").strip() or None
        email = data.get("email")
        phone = (data.get("phone") or "").strip()
        if tenant and email:
            queryset = Customer.objects.filter(tenant=tenant, email=email)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    {"email": "A customer with this email already exists."},
                )
        if self.instance is None and not email and not phone:
            raise serializers.ValidationError({"detail": "Provide an email or a phone number."})
        # Name composition: first/last wins over name when either is present.
        first = (data.get("first_name") or "").strip()
        last = (data.get("last_name") or "").strip()
        if first or last:
            data["name"] = " ".join(f"{first} {last}".split())
        if self.instance is None and not (data.get("name") or "").strip():
            raise serializers.ValidationError(
                {"name": "This field is required."},
            )
        return data

    def create(self, validated_data: dict) -> Customer:
        """Create the customer, converging identities per ADR-002.

        Rule 1: a payload phone matching an existing tenant user links that
        user instead of provisioning a second identity (synthetic/empty email
        → link + adopt the real email; a different real email → 400
        ``phone_already_registered``). A phone-only payload links the
        synthetic identity as-is — there is no email to adopt.

        An orphaned identity — a customer-role user whose customer row was
        deleted (issue #72) — is linked too, real email or not: there is no
        live account behind the phone. A contradicting payload email still
        rejects (the orphan's real email is never silently replaced); the
        same email or a phone-only payload adopts cleanly.

        No phone or no match → blessed provisioning flow; a phone-only
        payload provisions the portal user under the synthetic OTP email
        while ``Customer.email`` stays NULL.
        """
        first_name = validated_data.pop("first_name", "")
        last_name = validated_data.pop("last_name", "")
        user = validated_data.get("user")
        phone = (validated_data.get("phone") or "").strip()
        tenant = validated_data.get("tenant")

        if user is None and phone:
            match = self._phone_identity_match(tenant, phone)
            if match is not None:
                profile = Customer.objects.filter(user=match).first()
                if not self._is_synthetic_identity(match):
                    # A real-email identity is a live account — unless it is
                    # an orphaned customer-role user (issue #72: the customer
                    # row is gone), whose phone is adoptable when the payload
                    # does not contradict its real email.
                    orphan = profile is None and match.role == User.Role.CUSTOMER
                    payload_email = (validated_data.get("email") or "").strip().lower()
                    email_conflicts = bool(payload_email) and payload_email != (match.email or "").strip().lower()
                    if not orphan or email_conflicts:
                        raise serializers.ValidationError(
                            {
                                "phone": [
                                    serializers.ErrorDetail(
                                        "This phone is already registered to a different " "account. Resolve manually.",
                                        code="phone_already_registered",
                                    )
                                ]
                            },
                        )
                # ADR-002 rule 1: LINK the phone-keyed identity — a synthetic
                # OTP account or an orphaned one (issue #72) — and adopt the
                # real email (no-op for a phone-only payload). Its
                # OTP-provisioned customer row is adopted (OneToOne forbids a
                # second profile); an orphan gets a fresh profile on the SAME
                # user — never a second identity.
                self._converge_phone_identity(match, validated_data)
                validated_data["user"] = match
                if profile is not None:
                    return self._adopt_customer_profile(profile, validated_data)
                return super().create(validated_data)

        if user is None:
            user = self._provision_portal_user(validated_data, tenant, first_name, last_name)
            validated_data["user"] = user
        return super().create(validated_data)

    @staticmethod
    def _synthetic_otp_email(phone: str, tenant=None) -> str:
        """The synthetic email scheme used by the phone-OTP flow.

        Tenant-scoped via the shared helper (FBOS-011 §3.5); legacy callers
        without a tenant keep the old ``{phone}@fitnation.local`` shape.
        """
        if tenant is None:
            return f"{phone}{SYNTHETIC_EMAIL_DOMAIN}"
        return synthetic_otp_email(phone, tenant)

    def _is_synthetic_identity(self, user: User) -> bool:
        """True when the user's identity is a phone-keyed synthetic OTP
        account (synthetic email or no email at all) — safe to converge.

        Matches on the shared ``@fitnation.local`` domain so BOTH synthetic
        schemes — legacy ``{phone}@…`` and tenant-scoped ``{phone}.{tenant}@…``
        — are recognized without a data migration (FBOS-011 §3.5).
        """
        return not user.email or user.email.lower().endswith(SYNTHETIC_EMAIL_DOMAIN)

    def _phone_identity_match(self, tenant, phone: str):
        """Return the tenant user already holding this phone, if any."""
        return User.objects.filter(tenant=tenant, phone=phone).order_by("id").first()

    def _converge_phone_identity(self, user: User, validated_data: dict) -> None:
        """Replace a synthetic/empty email with the customer's real email.

        A phone-only payload (msg 2438) has no email to adopt — the linked
        user keeps its synthetic email untouched.
        """
        new_email = validated_data.get("email")
        if not new_email:
            return
        try:
            with transaction.atomic():
                user.email = new_email
                user.save(update_fields=["email", "updated_at"])
        except IntegrityError:
            raise serializers.ValidationError({"email": "A user with this email already exists."}) from None

    def _adopt_customer_profile(self, profile: Customer, validated_data: dict) -> Customer:
        """Apply the payload to an existing (OTP-provisioned) customer row."""
        for field in (
            "name",
            "email",
            "phone",
            "date_of_birth",
            "gender",
            "emergency_contact_name",
            "emergency_contact_phone",
        ):
            value = validated_data.get(field)
            if value:
                setattr(profile, field, value)
        # Phone-only payload: an OTP-provisioned row carries a synthetic
        # email — normalize it to the NULL-email shape a direct phone-only
        # create produces (msg 2438: Customer.email stays NULL). Both
        # synthetic schemes (legacy + tenant-scoped) share the domain.
        if not validated_data.get("email") and profile.email and profile.email.lower().endswith(SYNTHETIC_EMAIL_DOMAIN):
            profile.email = None
        if validated_data.get("branch"):
            profile.branch = validated_data["branch"]
        profile.is_active = True
        profile.save()
        return profile

    def update(self, instance: Customer, validated_data: dict) -> Customer:
        """Update the customer; write-only name parts never reach the model.

        ADR-002 rule 3: setting a phone on an email-only customer provisions
        OTP capability on the SAME linked user — never a second identity.
        Msg 2438: adding a real email to a synthetic-identity customer adopts
        it onto the SAME user (atomic; a collision → 400 field error) — a
        non-synthetic user email is never overwritten.
        """
        validated_data.pop("first_name", None)
        validated_data.pop("last_name", None)
        self._adopt_real_email(instance, validated_data)
        customer = super().update(instance, validated_data)
        new_phone = validated_data.get("phone")
        if new_phone and customer.user and not customer.user.phone:
            customer.user.phone = new_phone
            customer.user.save(update_fields=["phone"])
        return customer

    def _adopt_real_email(self, instance: Customer, validated_data: dict) -> None:
        """Adopt a real payload email onto a synthetic-identity customer.

        Runs before the customer row update so an email collision rolls back
        cleanly (400, nothing written). Only a synthetic user (synthetic/empty
        email) whose customer email is still NULL/matching-synthetic is
        eligible; the adopted account stays verified — the owner vouches.
        """
        new_email = (validated_data.get("email") or "").strip()
        if not new_email or not instance.user_id:
            return
        user = instance.user
        if not self._is_synthetic_identity(user):
            return
        if instance.email and instance.email != user.email:
            return
        try:
            with transaction.atomic():
                user.email = new_email
                user.is_email_verified = True
                user.save(update_fields=["email", "is_email_verified", "updated_at"])
        except IntegrityError:
            raise serializers.ValidationError({"email": "A user with this email already exists."}) from None
        validated_data["email"] = new_email

    def _provision_portal_user(self, validated_data, tenant, first_name: str, last_name: str) -> User:
        """Auto-provision the linked customer-role portal account.

        Unusable password (customers authenticate via OTP); the owner vouches
        for the email so the account starts verified. A phone-only customer
        (msg 2438) is provisioned under the tenant-scoped synthetic OTP email
        (:func:`apps.users.services.synthetic_otp_email`) — the same scheme as
        the phone-OTP flow, so a later OTP login reuses this identity. Email
        conflicts surface as a 400 field error — never silently link an
        existing user.
        """
        email = validated_data.get("email")
        if not email:
            phone = (validated_data.get("phone") or "").strip()
            email = self._synthetic_otp_email(phone, tenant) if phone else None
        try:
            # Nested atomic: a uniqueness violation rolls back to the savepoint
            # so the surrounding request transaction stays usable for the 400.
            with transaction.atomic():
                user = User.objects.create_user(
                    email=email,
                    password=None,
                    first_name=first_name,
                    last_name=last_name,
                    role=User.Role.CUSTOMER,
                    tenant=tenant,
                    phone=validated_data.get("phone") or "",
                )
        except IntegrityError:
            raise serializers.ValidationError(
                {"email": "A user with this email already exists."},
            ) from None
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        return user


class HealthProfileSerializer(serializers.ModelSerializer):
    """Serialize health profile details."""

    class Meta:
        """Serializer metadata."""

        model = HealthProfile
        fields: ClassVar[list[str]] = [
            "id",
            "customer",
            "height_cm",
            "weight_kg",
            "bmi",
            "blood_group",
            "injuries",
            "current_injuries",
            "past_injuries",
            "medical_info",
            "medical_conditions",
            "allergies",
            "food_allergies",
            "medications",
            "dietary_restrictions",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "bmi", "created_at", "updated_at"]


class FitnessGoalSerializer(serializers.ModelSerializer):
    """Serialize fitness goal details."""

    progress_percentage = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata."""

        model = FitnessGoal
        fields: ClassVar[list[str]] = [
            "id",
            "customer",
            "goal_type",
            "is_active",
            "status",
            "target_value",
            "target_unit",
            "target_date",
            "current_value",
            "progress_percentage",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "created_at", "updated_at"]

    def get_progress_percentage(self, obj: FitnessGoal) -> float | None:
        """Return the computed goal progress percentage."""
        return obj.progress_percentage


class BodyMeasurementSerializer(serializers.ModelSerializer):
    """Serialize body measurement details."""

    class Meta:
        """Serializer metadata."""

        model = BodyMeasurement
        fields: ClassVar[list[str]] = [
            "id",
            "customer",
            "date_logged",
            "weight_kg",
            "height_cm",
            "bmi",
            "body_fat_percentage",
            "chest_cm",
            "waist_cm",
            "hips_cm",
            "biceps_cm",
            "thighs_cm",
            "neck_cm",
            "arms_cm",
            "legs_cm",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "bmi", "date_logged", "created_at", "updated_at"]


class ProgressPhotoSerializer(serializers.ModelSerializer):
    """Serialize progress photo details."""

    class Meta:
        """Serializer metadata."""

        model = ProgressPhoto
        fields: ClassVar[list[str]] = [
            "id",
            "customer",
            "image",
            "caption",
            "taken_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "customer", "taken_at", "created_at", "updated_at"]
