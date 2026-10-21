"""Onboarding serializers — the wizard's request contract (onboarding-design §3.4)."""

from rest_framework import serializers

from apps.onboarding.models import OnboardingSession

PAYMENT_METHODS = ("cash", "card", "upi", "bank_transfer", "other", "razorpay")

# Maps the wizard's payment-method vocabulary onto Payment.PaymentMethod.
# Razorpay is recorded as an online payment (completed only at verify time).
METHOD_TO_PAYMENT_METHOD = {
    "cash": "cash",
    "card": "card",
    "upi": "upi",
    "bank_transfer": "bank_transfer",
    "other": "other",
    "razorpay": "online",
}


class OnboardingCustomerSerializer(serializers.Serializer):
    """Who is being onboarded — mirrors ``POST /customers/`` semantics."""

    phone = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    date_of_birth = serializers.DateField(required=False, allow_null=True, default=None)
    gender = serializers.ChoiceField(
        choices=["male", "female", "other", "prefer_not_to_say"],
        required=False,
        default="prefer_not_to_say",
    )
    branch = serializers.IntegerField()
    emergency_contact_name = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    emergency_contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, data: dict) -> dict:
        """Require a name in some form (full name or first/last parts)."""
        if not (data.get("name") or "").strip() and not ((data.get("first_name") or "").strip()):
            raise serializers.ValidationError({"name": "Provide a name (or first/last name)."})
        return data

    def to_customer_payload(self) -> dict:
        """Render as the ``CustomerSerializer`` create payload."""
        data = {
            "phone": self.validated_data["phone"],
            "branch": self.validated_data["branch"],
            "gender": self.validated_data.get("gender") or "prefer_not_to_say",
        }
        for src, dst in (
            ("name", "name"),
            ("first_name", "first_name"),
            ("last_name", "last_name"),
            ("date_of_birth", "date_of_birth"),
            ("emergency_contact_name", "emergency_contact_name"),
            ("emergency_contact_phone", "emergency_contact_phone"),
            ("notes", "notes"),
        ):
            value = self.validated_data.get(src)
            if value:
                data[dst] = value
        email = (self.validated_data.get("email") or "").strip()
        if email:
            data["email"] = email
        return data


class OnboardingMembershipSerializer(serializers.Serializer):
    """Which plan and validity window to assign."""

    plan = serializers.IntegerField()
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)


class OnboardingPaymentSerializer(serializers.Serializer):
    """Desk payment (omit the whole block for ₹0 trials)."""

    method = serializers.ChoiceField(choices=list(PAYMENT_METHODS))
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class OnboardingBiometricSerializer(serializers.Serializer):
    """One device credential captured at the desk."""

    device = serializers.IntegerField()
    credential_type = serializers.ChoiceField(
        choices=["fingerprint", "face", "card", "pin", "qr"],
        required=False,
        default="fingerprint",
    )
    device_user_id = serializers.CharField(max_length=64)


class OnboardingMemberSerializer(serializers.Serializer):
    """The single POST payload for the whole wizard."""

    customer = OnboardingCustomerSerializer()
    membership = OnboardingMembershipSerializer()
    payment = OnboardingPaymentSerializer(required=False, allow_null=True)
    biometrics = OnboardingBiometricSerializer(many=True, required=False, default=list)
    send_welcome = serializers.BooleanField(required=False, default=True)
    send_app_invite = serializers.BooleanField(required=False, default=True)


class OnboardingVerifyPaymentSerializer(serializers.Serializer):
    """Razorpay checkout callback for the two-phase flow."""

    razorpay_order_id = serializers.CharField()
    razorpay_payment_id = serializers.CharField()
    razorpay_signature = serializers.CharField()


def session_result_payload(session: OnboardingSession) -> dict:
    """Return the stored composite result for a session (replay path).

    Args:
        session: The previously-created onboarding session.

    Returns:
        The stored result dict.
    """
    return session.result or {}
