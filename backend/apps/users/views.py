"""User and authentication API views."""

import logging
from collections.abc import Callable
from typing import ClassVar

from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from apps.branches.models import Branch
from apps.notifications.models import NotificationLog
from apps.notifications.services.router import send_verification_message
from apps.permissions.models import Role, UserRoleAssignment
from apps.permissions.permissions import RolePermission
from apps.tenants.models import Tenant
from apps.tenants.permissions import IsTenantMember
from apps.users.auth import AuthToken
from apps.users.authentication import TenantTokenAuthentication
from apps.users.firebase_auth import (
    FirebaseRateLimited,
    FirebaseTokenError,
    FirebaseVerifierUnavailableError,
    firebase_verify_phone,
    throttle_failed_verification,
)
from apps.users.models import EmailVerificationToken
from apps.users.otp import (
    OtpDeliveryError,
    OtpError,
    OtpRateLimited,
    issue_otp,
    resolve_otp_senders,
    verify_otp,
)
from apps.users.selectors import user_get_by_id, user_list
from apps.users.serializers import (
    FirebaseAuthSerializer,
    LoginSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    TrainerCreateSerializer,
    TrainerCustomerAssignmentSerializer,
    TrainerMetricsSerializer,
    TrainerScheduleSerializer,
    TrainerSerializer,
    TrainerUpdateSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from apps.users.services import (
    AutoProvisionLimitReached,
    TenantResolutionError,
    build_entitlement_payload,
    create_user,
    delete_customer_account,
    get_effective_permissions,
    get_or_create_customer_by_phone,
    get_user_permissions,
    issue_token,
    resolve_tenant_for_otp,
)
from apps.users.trainer_selectors import (
    trainer_assignment_list,
    trainer_get_by_id,
    trainer_list,
    trainer_metrics,
    trainer_schedule_list,
)
from apps.users.trainer_services import (
    assign_customer_to_trainer,
    create_schedule,
    create_trainer,
    unassign_customer_from_trainer,
    update_schedule,
    update_trainer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class LoginView(APIView):
    """Authenticate an email/password pair and issue an auth token."""

    authentication_classes: ClassVar[list] = []
    permission_classes: ClassVar[list] = [AllowAny]

    def post(self, request: Request) -> Response:
        """Handle login."""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Case-insensitive login: resolve the stored email form (Postgres
        # lookups are case-sensitive; users may type any casing).
        email = data["email"].strip().lower()
        stored = User.objects.filter(email__iexact=email).first()
        if stored is not None:
            data["email"] = stored.email

        user = authenticate(
            request,
            username=data["email"],
            password=data["password"],
        )
        if user is None:
            raise AuthenticationFailed("Invalid credentials")
        if not user.is_active:
            raise AuthenticationFailed("Account is inactive")

        tenant = user.tenant
        if tenant and tenant.status != Tenant.Status.ACTIVE:
            raise AuthenticationFailed("Tenant is not active")

        token = issue_token(user, tenant, device_type=data.get("device_type", ""))
        permissions = get_user_permissions(user)
        return Response(
            {
                "token": token.key,
                "user": UserSerializer(user).data,
                "permissions": permissions,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """Deactivate the current auth token."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Handle logout."""
        token = request.auth
        if isinstance(token, AuthToken):
            token.is_active = False
            token.save(update_fields=["is_active"])
        return Response({"message": "Logged out successfully"})


class DeleteAccountView(APIView):
    """Delete the calling CUSTOMER's own account (spec §8 task B8).

    Google Play mandates an in-app account-deletion path for any app that
    stores personal data — this one stores health data — so this endpoint is
    the deletion path for the member app. It acts on ``request.user`` only:
    there is no body, no target identifier, and staff accounts are
    rejected (staff/offboarding belongs to user management, not this
    privacy flow).

    Retention decision (see :func:`delete_customer_account` in
    apps/users/services.py for the field-level detail):

    * Anonymised in place — ``User`` first_name/last_name/email/phone and
      the linked ``Customer`` name/email/phone/dob/gender/emergency
      contacts/addresses/notes are scrubbed to neutral values; the rows
      stay so business records keep their keys but cannot be linked back
      to a natural person.
    * Purged — health data (health profile, measurements, goals, progress
      photos), the user's OTP rows (per-tenant), push device tokens
      (per-tenant) and all auth tokens (every device is logged out).
    * Retained but non-identifying — memberships, payments, invoices,
      attendance and other business records for statutory/financial
      reasons; Google Play allows retaining such records for legal
      obligations while the personal identity around them is erased.
    * Multi-tenant — only rows within ``request.tenant`` are touched.
    """

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember]

    def post(self, request: Request) -> Response:
        """Anonymise + deactivate the caller's account, then end the response."""
        if request.user.role != User.Role.CUSTOMER:
            return Response(
                {"detail": "Only customer accounts can be deleted through this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )
        delete_customer_account(request.user, request.tenant)
        return Response({"message": "Account deleted"})


class MeView(APIView):
    """Return the current authenticated user profile."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember]

    def get(self, request: Request) -> Response:
        """Return current user data with effective permissions + entitlement.

        Customers get role permissions plus the entitlement-derived
        ``app.access`` code (only while entitled), and the ``entitlement``
        object the app's gate reads. Staff keep the role-only list and
        ``entitlement: null`` (FBOS-011 §2.3b).
        """
        return Response(
            {
                "user": UserSerializer(request.user).data,
                "permissions": get_effective_permissions(request.user, request.tenant),
                "entitlement": build_entitlement_payload(request.user, request.tenant),
            }
        )


class EntitlementView(APIView):
    """Live app-access entitlement for the current user (FBOS-011 §2.3c).

    The mobile app calls this on app resume (throttled client-side);
    ``/auth/me/`` remains the login-time source. No role permission — a
    gated-out member must still be able to see WHY they're gated.
    """

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember]

    def get(self, request: Request) -> Response:
        """Return the entitlement object (status ``none`` for staff rows)."""
        entitlement = build_entitlement_payload(request.user, request.tenant)
        if entitlement is None:
            from apps.memberships.selectors import get_app_entitlement

            empty = get_app_entitlement(None, tenant=request.tenant)
            gym = {"uuid": str(request.tenant.uuid), "name": request.tenant.name} if request.tenant else None
            entitlement = {**empty.as_payload(), "gym": gym}
        return Response(entitlement)


def _client_ip(request: Request) -> str | None:
    """Client IP for rate limits (Cloud Run sets X-Forwarded-For)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR") or None


def _phone_login_session_response(
    phone: str,
    gym_anchor,
    device_type: str,
    ip: str | None,
    tenant_gate: Callable[[Tenant], Response | None] | None = None,
) -> Response:
    """The ONE convergence path for phone-keyed customer logins (FBOS-011 §3).

    Tenant resolution → optional per-route credential gate → identity
    convergence → token issuance → the mobile response payload. Both
    ``POST /auth/otp/verify/`` and ``POST /auth/firebase/`` funnel through
    here so the anchor ladder, the auto-provision cap and the response
    contract (token / user / effective permissions / entitlement — never
    revealing registration state) cannot drift between the two routes.

    Args:
        phone: The verified phone number in E.164.
        gym_anchor: Optional device-bound gym anchor (tenant uuid).
        device_type: ``AuthToken.DeviceType`` value for the issued session.
        ip: Client IP for the anchor rate limit.
        tenant_gate: Optional route-specific credential check run once the
            tenant is resolved — returns a ``Response`` to short-circuit
            (e.g. a wrong OTP code → 400) or ``None`` to continue. The
            Firebase route has already verified its ID token and passes
            nothing.

    Returns:
        The DRF ``Response``: the success payload, the 200 disambiguation
        payload (phone registered at several gyms), or the mapped 4xx
        resolution / auto-provision error.
    """
    try:
        tenant, disambiguation = resolve_tenant_for_otp(phone, gym_anchor, ip=ip)
    except TenantResolutionError as exc:
        return Response(exc.detail, status=exc.status_code)
    if disambiguation is not None:
        return Response(disambiguation, status=200)

    if tenant_gate is not None:
        gate_response = tenant_gate(tenant)
        if gate_response is not None:
            return gate_response

    try:
        user = get_or_create_customer_by_phone(phone, tenant)
    except AutoProvisionLimitReached as exc:
        return Response(exc.detail, status=exc.status_code)
    token = issue_token(user, tenant, device_type=device_type)
    return Response(
        {
            "token": token.key,
            "user": UserSerializer(user).data,
            "permissions": get_effective_permissions(user, tenant),
            "entitlement": build_entitlement_payload(user, tenant),
        }
    )


class OTPRequestView(APIView):
    """Request a real OTP (gym anchors + real delivery chain, FBOS-011 §4)."""

    authentication_classes: ClassVar[list] = []
    permission_classes: ClassVar[list] = [AllowAny]

    def post(self, request: Request) -> Response:
        """Resolve the gym anchor, then issue + deliver a hashed 6-digit OTP.

        Delivery walks the per-tenant sender chain (WATI → Gupshup → SMS);
        total chain failure is a loud 503 — never a silent log-file drop,
        and a WhatsApp leg whose template is unapproved degrades to SMS
        instead of trusting Gupshup's 202 ack (#74). The 200 body's
        ``delivery`` channel tells the app which way the code went
        (sent-ok over WhatsApp vs degraded to SMS) — it is never a
        registration signal. The code is echoed in the response ONLY behind
        DEBUG with the stub sender.
        """
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        gym_anchor = serializer.validated_data.get("gym")
        ip = _client_ip(request)

        try:
            tenant, disambiguation = resolve_tenant_for_otp(phone, gym_anchor, ip=ip)
        except TenantResolutionError as exc:
            return Response(exc.detail, status=exc.status_code)
        if disambiguation is not None:
            return Response(disambiguation, status=status.HTTP_200_OK)

        senders = resolve_otp_senders(tenant)
        try:
            result = issue_otp(phone, tenant, ip=ip, sender=senders)
        except OtpRateLimited as exc:
            return Response({"detail": str(exc)}, status=429)
        except OtpError as exc:
            return Response({"detail": str(exc)}, status=400)
        except OtpDeliveryError as exc:
            logger.critical(
                "OTP delivery unavailable (tenant=%s, channels=%s) — 503 returned",
                tenant.pk,
                exc.channels,
            )
            return Response(
                {
                    "detail": "OTP delivery is temporarily unavailable — please contact the gym.",
                    "code": "otp_delivery_unavailable",
                    # Machine-readable per-leg reasons (not_configured /
                    # template_not_approved / provider_error / http_<status>/…)
                    # so the app + operator can see WHY. No secrets, no
                    # provider detail beyond the reason codes.
                    "channels": exc.channels,
                },
                status=503,
            )

        data = {
            "phone": phone,
            "expires_in": result.expires_in,
            "sent": True,
            # Semantic channel that carried the code: whatsapp = sent-ok,
            # sms = degraded — the app can prompt "check your messages" (#74).
            "delivery": result.channel,
        }
        stub = next((s for s in senders if getattr(s, "name", "") == "stub"), None)
        if stub is not None:  # DEBUG/test only — never in production
            data["otp"] = getattr(stub, "code", None)
        return Response(data)


class OTPVerifyView(APIView):
    """Verify the real OTP and return an auth token (anchors + entitlement)."""

    authentication_classes: ClassVar[list] = []
    permission_classes: ClassVar[list] = [AllowAny]

    def post(self, request: Request) -> Response:
        """Validate the code, converge the identity and issue a token.

        The response carries effective permissions (``app.access`` only while
        entitled) and the ``entitlement`` object (FBOS-011 §2.3a/§3):
        auto-provisioned or membership-less phones still get a token — the
        response never reveals registration state — but with entitlement
        ``none`` so the app shows "ask your gym for access" instead of a hard
        error.
        """
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        def check_otp_code(tenant: Tenant) -> Response | None:
            """Consume the code against the resolved tenant (400 on mismatch)."""
            try:
                verify_otp(data["phone"], data["otp"], tenant=tenant)
            except OtpError as exc:
                return Response({"detail": str(exc)}, status=400)
            return None

        return _phone_login_session_response(
            data["phone"],
            data.get("gym"),
            data.get("device_type", AuthToken.DeviceType.ANDROID),
            _client_ip(request),
            tenant_gate=check_otp_code,
        )


class FirebaseAuthView(APIView):
    """Exchange a Firebase ID token for a session (customer-app phone login).

    The Flutter app signs the member in with Firebase phone OTP inside the
    mobile app's own Firebase project (``yougetfitwithus``) and swaps the
    resulting ID token here. Beyond the token check, convergence is byte-for-
    byte the OTP-verify path (:func:`_phone_login_session_response`): the
    same anchor ladder, the same identity convergence, and the identical
    response JSON — token, user, effective permissions and the entitlement
    object, including the never-reveal-registration-state rule (entitlement
    ``none`` → the app shows "ask your gym for access", never an error).

    Verdict mapping (fail closed):

    * invalid/expired/unverifiable token → 401, after counting the failure
      against a per-IP daily cap that answers 429 once exceeded (successes
      never count);
    * verifier broken at runtime (transport/backend) → 503;
    * credentials/project misconfigured → loud 503 naming the missing piece
      after CRITICAL logging (ops action) — never a silent fallback that
      could accept a wrong project's tokens.
    """

    authentication_classes: ClassVar[list] = []
    permission_classes: ClassVar[list] = [AllowAny]

    def post(self, request: Request) -> Response:
        """Verify the ID token, then converge exactly like OTP verify."""
        serializer = FirebaseAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ip = _client_ip(request)

        try:
            phone = firebase_verify_phone(data["id_token"])
        except ImproperlyConfigured as exc:
            logger.critical("Firebase auth misconfigured — failing closed: %s", exc)
            return Response(
                {"detail": str(exc), "code": "firebase_auth_misconfigured"},
                status=503,
            )
        except FirebaseVerifierUnavailableError as exc:
            logger.error("Firebase verification unavailable — 503 returned: %s", exc)
            return Response(
                {
                    "detail": "Phone login is temporarily unavailable — please try again.",
                    "code": "firebase_auth_unavailable",
                },
                status=503,
            )
        except FirebaseTokenError as exc:
            try:
                throttle_failed_verification(ip)
            except FirebaseRateLimited:
                return Response({"detail": "Too many requests. Try again later."}, status=429)
            return Response({"detail": str(exc)}, status=401)

        return _phone_login_session_response(
            phone,
            data.get("gym"),
            data.get("device_type", AuthToken.DeviceType.ANDROID),
            ip,
        )


class VerifyEmailView(APIView):
    """Verify a user's email address using a token."""

    authentication_classes: ClassVar[list] = []
    permission_classes: ClassVar[list] = [AllowAny]

    def get(self, request: Request, token: str) -> Response:
        """Verify the email token."""
        try:
            verification = EmailVerificationToken.objects.select_related("user").get(
                token=token,
                is_used=False,
            )
        except EmailVerificationToken.DoesNotExist:
            return Response(
                {"error": "Invalid or expired verification link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not verification.is_valid():
            return Response(
                {"error": "This verification link has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = verification.user
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

        verification.is_used = True
        verification.save(update_fields=["is_used"])

        return Response(
            {"message": "Your email has been verified successfully!"},
            status=status.HTTP_200_OK,
        )


class ResendVerificationEmailView(APIView):
    """Resend the verification email to the unverified user."""

    authentication_classes: ClassVar[list] = []
    permission_classes: ClassVar[list] = [AllowAny]

    def post(self, request: Request) -> Response:
        """Send a new verification email."""
        email = request.data.get("email", "").strip()
        if not email:
            return Response(
                {"error": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        User = get_user_model()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal whether email exists
            return Response(
                {"message": "If that email is registered, a verification link has been sent."},
                status=status.HTTP_200_OK,
            )

        # Don't reveal whether email is verified (no account enumeration)
        if user.is_email_verified:
            return Response(
                {"message": "If that email is registered, a verification link has been sent."},
                status=status.HTTP_200_OK,
            )

        # Channel policy (issue #66): the tenant's WhatsApp carries the link
        # when configured; email is the last resort.
        log = send_verification_message(user, request)
        if log.status == NotificationLog.Status.SENT:
            return Response(
                {"message": "Verification sent — check your WhatsApp or email inbox."},
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"error": "Failed to send verification message. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserViewSet(ViewSet):
    """Tenant-scoped user management CRUD."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "users.view_user"

    def get_serializer_class(self) -> type:
        """Return the serializer class for the current action."""
        if self.action == "create":
            return UserCreateSerializer
        if self.action in {"update", "partial_update"}:
            return UserUpdateSerializer
        return UserSerializer

    def list(self, request: Request) -> Response:
        """List users in the current tenant."""
        qs = user_list(
            tenant=request.tenant,
            role=request.query_params.get("role"),
            branch_id=request.query_params.get("branch_id"),
            is_active=request.query_params.get("is_active"),
            search=request.query_params.get("search"),
        )
        serializer = UserSerializer(qs, many=True)
        return Response(serializer.data)

    def create(self, request: Request) -> Response:
        """Create a new user in the tenant."""
        self.required_permission = "users.create_user"
        serializer = UserCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = create_user(
            tenant=request.tenant,
            email=data["email"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone=data.get("phone", ""),
            role=data["role"],
            password=data.get("password", ""),
            branch_id=data.get("branch_id"),
            actor=request.user,
        )
        # Send verification for non-owner roles — channel-aware (#66): the
        # gym's WhatsApp carries the link when configured, email otherwise.
        User = get_user_model()
        if user.role != User.Role.GYM_OWNER and not user.is_owner:
            send_verification_message(user, request)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request: Request, pk: int) -> Response:
        """Retrieve a single tenant-scoped user."""
        user = user_get_by_id(request.tenant, int(pk))
        serializer = UserSerializer(user)
        return Response(serializer.data)

    def partial_update(self, request: Request, pk: int) -> Response:
        """Update a tenant-scoped user."""
        self.required_permission = "users.edit_user"
        user = user_get_by_id(request.tenant, int(pk))
        serializer = UserUpdateSerializer(
            user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="assign-branch")
    def assign_branch(self, request: Request, pk: int) -> Response:
        """Assign the user to a branch with a branch-scoped role."""
        self.required_permission = "users.edit_user"
        user = user_get_by_id(request.tenant, int(pk))
        branch_id = request.data.get("branch_id")
        role_at_branch = request.data.get("role_at_branch", user.role)

        if branch_id is None:
            raise ValidationError("branch_id is required")

        try:
            branch = Branch.objects.for_tenant(request.tenant).get(id=int(branch_id))
        except (Branch.DoesNotExist, ValueError) as exc:
            raise ValidationError("Invalid branch_id") from exc

        assignment, created = UserRoleAssignment.objects.get_or_create(
            user=user,
            role=Role.objects.get_or_create(
                code=role_at_branch,
                defaults={"name": role_at_branch, "is_system_role": False},
            )[0],
            branch=branch,
            defaults={"assigned_by": request.user, "is_active": True},
        )
        if not created:
            assignment.is_active = True
            assignment.assigned_by = request.user
            assignment.save()

        return Response(
            {
                "message": "User assigned to branch",
                "assignment_id": assignment.id,
                "branch_id": branch.id,
                "role_at_branch": role_at_branch,
            }
        )


# ── Trainer ViewSet ───────────────────────────────────────────────────────────


class TrainerViewSet(ViewSet):
    """Tenant-scoped trainer management CRUD with schedule, assignment, and metrics."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "users.view_user"

    def _get_trainer(self, request: Request, pk: int):
        """Retrieve a trainer or raise 404."""
        from apps.users.models import Trainer

        try:
            return trainer_get_by_id(request.tenant, int(pk))
        except Trainer.DoesNotExist as exc:
            raise NotFound("Trainer not found") from exc

    def list(self, request: Request) -> Response:
        """List trainers in the current tenant."""
        qs = trainer_list(
            tenant=request.tenant,
            is_active=request.query_params.get("is_active"),
            specialization=request.query_params.get("specialization"),
            search=request.query_params.get("search"),
        )
        serializer = TrainerSerializer(qs, many=True)
        return Response(serializer.data)

    def create(self, request: Request) -> Response:
        """Create a new trainer in the tenant."""
        self.required_permission = "users.create_user"
        serializer = TrainerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            trainer = create_trainer(
                tenant=request.tenant,
                email=data["email"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                phone=data.get("phone", ""),
                password=data.get("password", ""),
                specialization=data.get("specialization", ""),
                bio=data.get("bio", ""),
                certifications=data.get("certifications", []),
                experience_years=data.get("experience_years", 0),
                max_clients=data.get("max_clients", 50),
                profile_photo=data.get("profile_photo", ""),
                actor=request.user,
            )
        except IntegrityError as exc:
            # Safety net: a constraint the serializer check missed (e.g. a
            # concurrent insert winning the email race) is a client error,
            # never a 500.
            raise ValidationError({"detail": "A user with this email already exists."}) from exc
        # Trainer invitation (#66): the verification link rides the gym's
        # WhatsApp when configured; email is the last resort.
        send_verification_message(trainer.user, request)
        return Response(TrainerSerializer(trainer).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request: Request, pk: int) -> Response:
        """Retrieve a single trainer."""
        trainer = self._get_trainer(request, pk)
        serializer = TrainerSerializer(trainer)
        return Response(serializer.data)

    def partial_update(self, request: Request, pk: int) -> Response:
        """Update a trainer profile."""
        self.required_permission = "users.edit_user"
        trainer = self._get_trainer(request, pk)
        serializer = TrainerUpdateSerializer(
            trainer,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        trainer = update_trainer(trainer, **serializer.validated_data)
        return Response(TrainerSerializer(trainer).data)

    @action(detail=True, methods=["get", "post"], url_path="schedule")
    def schedule(self, request: Request, pk: int) -> Response:
        """GET: List trainer's schedule. POST: Add a schedule entry."""
        trainer = self._get_trainer(request, pk)

        if request.method == "GET":
            schedules = trainer_schedule_list(request.tenant, trainer.id)
            serializer = TrainerScheduleSerializer(schedules, many=True)
            return Response(serializer.data)

        # POST — create new schedule entry
        self.required_permission = "users.edit_user"
        serializer = TrainerScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        schedule = create_schedule(
            tenant=request.tenant,
            trainer=trainer,
            day_of_week=data["day_of_week"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            is_available=data.get("is_available", True),
        )
        return Response(
            TrainerScheduleSerializer(schedule).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["patch"],
        url_path=r"schedule/(?P<schedule_id>\d+)",
    )
    def update_schedule(self, request: Request, pk: int, schedule_id: int) -> Response:
        """PATCH: Update a specific schedule entry."""
        self.required_permission = "users.edit_user"
        trainer = self._get_trainer(request, pk)
        from apps.users.models import TrainerSchedule

        try:
            schedule = TrainerSchedule.objects.get(
                id=schedule_id,
                tenant=request.tenant,
                trainer=trainer,
            )
        except TrainerSchedule.DoesNotExist as exc:
            raise NotFound("Schedule entry not found") from exc

        serializer = TrainerScheduleSerializer(schedule, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        schedule = update_schedule(schedule, **data)
        return Response(TrainerScheduleSerializer(schedule).data)

    @action(detail=True, methods=["post"], url_path="assign-customer")
    def assign_customer(self, request: Request, pk: int) -> Response:
        """Assign a customer to this trainer."""
        self.required_permission = "users.edit_user"
        trainer = self._get_trainer(request, pk)
        customer_id = request.data.get("customer_id")

        if customer_id is None:
            raise ValidationError("customer_id is required")

        from apps.customers.models import Customer

        try:
            customer = Customer.objects.get(id=int(customer_id), tenant=request.tenant)
        except (Customer.DoesNotExist, ValueError) as exc:
            raise NotFound("Customer not found") from exc

        assignment = assign_customer_to_trainer(
            tenant=request.tenant,
            trainer=trainer,
            customer_id=customer.id,
        )
        return Response(
            TrainerCustomerAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="assignments")
    def assignments(self, request: Request, pk: int) -> Response:
        """List customer assignments for a trainer."""
        trainer = self._get_trainer(request, pk)
        is_active = request.query_params.get("is_active")
        if is_active is not None and isinstance(is_active, str):
            is_active = is_active.lower() in ("true", "1", "yes")
        qs = trainer_assignment_list(
            tenant=request.tenant,
            trainer_id=trainer.id,
            is_active=is_active,
        )
        serializer = TrainerCustomerAssignmentSerializer(qs, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"unassign-customer/(?P<assignment_id>\d+)",
    )
    def unassign_customer(self, request: Request, pk: int, assignment_id: int) -> Response:
        """Unassign a customer from this trainer."""
        self.required_permission = "users.edit_user"
        trainer = self._get_trainer(request, pk)
        from apps.users.models import TrainerCustomerAssignment

        try:
            assignment = TrainerCustomerAssignment.objects.get(
                id=assignment_id,
                tenant=request.tenant,
                trainer=trainer,
            )
        except TrainerCustomerAssignment.DoesNotExist as exc:
            raise NotFound("Assignment not found") from exc

        assignment = unassign_customer_from_trainer(assignment)
        return Response(TrainerCustomerAssignmentSerializer(assignment).data)

    @action(detail=True, methods=["get"], url_path="metrics")
    def performance_metrics(self, request: Request, pk: int) -> Response:
        """Return aggregate performance metrics for a trainer."""
        trainer = self._get_trainer(request, pk)
        metrics = trainer_metrics(request.tenant, trainer.id)
        serializer = TrainerMetricsSerializer(data=metrics)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)
