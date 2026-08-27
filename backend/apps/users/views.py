"""User and authentication API views."""

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from apps.branches.models import Branch
from apps.core.services.email import send_verification_email
from apps.permissions.models import Role, UserRoleAssignment
from apps.permissions.permissions import RolePermission
from apps.tenants.models import Tenant
from apps.tenants.permissions import IsTenantMember
from apps.users.auth import AuthToken
from apps.users.authentication import TenantTokenAuthentication
from apps.users.models import EmailVerificationToken
from apps.users.selectors import user_get_by_id, user_list
from apps.users.serializers import (
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
    create_user,
    get_or_create_customer_by_phone,
    get_user_permissions,
    issue_token,
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


class LoginView(APIView):
    """Authenticate an email/password pair and issue an auth token."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        """Handle login."""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

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

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Handle logout."""
        token = request.auth
        if isinstance(token, AuthToken):
            token.is_active = False
            token.save(update_fields=["is_active"])
        return Response({"message": "Logged out successfully"})


class MeView(APIView):
    """Return the current authenticated user profile."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get(self, request: Request) -> Response:
        """Return current user data."""
        return Response(
            {
                "user": UserSerializer(request.user).data,
                "permissions": get_user_permissions(request.user),
            }
        )


class OTPRequestView(APIView):
    """Request a fake deterministic OTP for mobile login."""

    authentication_classes = []
    permission_classes = [AllowAny]

    FAKE_OTP = "123456"

    def post(self, request: Request) -> Response:
        """Return the deterministic fake OTP."""
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        return Response(
            {
                "phone": phone,
                "otp": self.FAKE_OTP,
                "expires_in_seconds": 300,
                "message": "OTP generated (stub).",
            }
        )


class OTPVerifyView(APIView):
    """Verify the fake deterministic OTP and return an auth token."""

    authentication_classes = []
    permission_classes = [AllowAny]

    EXPECTED_OTP = "123456"

    def post(self, request: Request) -> Response:
        """Validate OTP and issue a token."""
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data["otp"] != self.EXPECTED_OTP:
            raise ValidationError("Invalid OTP")

        tenant = request.tenant
        if tenant is None:
            tenant = Tenant.objects.first()
            if tenant is None:
                raise ValidationError("No tenant available for OTP login")

        user = get_or_create_customer_by_phone(data["phone"], tenant)
        token = issue_token(
            user,
            tenant,
            device_type=data.get("device_type", AuthToken.DeviceType.ANDROID),
        )
        permissions = get_user_permissions(user)
        return Response(
            {
                "token": token.key,
                "user": UserSerializer(user).data,
                "permissions": permissions,
            }
        )


class VerifyEmailView(APIView):
    """Verify a user's email address using a token."""

    authentication_classes = []
    permission_classes = [AllowAny]

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

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        """Send a new verification email."""
        email = request.data.get("email", "").strip()
        if not email:
            return Response(
                {"error": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal whether email exists
            return Response(
                {"message": "If that email is registered, a verification link has been sent."},
                status=status.HTTP_200_OK,
            )

        if user.is_email_verified:
            return Response(
                {"message": "This email is already verified."},
                status=status.HTTP_200_OK,
            )

        sent = send_verification_email(user, request)
        if sent:
            return Response(
                {"message": "Verification email sent. Check your inbox (and spam)."},
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"error": "Failed to send verification email. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserViewSet(ViewSet):
    """Tenant-scoped user management CRUD."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
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
        # Send email verification for non-owner roles
        if user.role != User.Role.GYM_OWNER and not user.is_owner:
            send_verification_email(user, request)
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

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
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
        # Send email verification to newly created trainer
        send_verification_email(trainer.user, request)
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
