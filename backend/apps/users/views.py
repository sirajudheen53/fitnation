"""User and authentication API views."""

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from apps.branches.models import Branch
from apps.permissions.models import Role, UserRoleAssignment
from apps.permissions.permissions import RolePermission
from apps.tenants.models import Tenant
from apps.tenants.permissions import IsTenantMember
from apps.users.auth import AuthToken
from apps.users.authentication import TenantTokenAuthentication
from apps.users.selectors import user_get_by_id, user_list
from apps.users.serializers import (
    LoginSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
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
