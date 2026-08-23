"""Customer management API views."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.customers.models import BodyMeasurement, Customer, FitnessGoal, HealthProfile
from apps.customers.serializers import (
    BodyMeasurementSerializer,
    CustomerSerializer,
    FitnessGoalSerializer,
    HealthProfileSerializer,
)
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


class CustomerViewSet(ModelViewSet):
    """Tenant-scoped customer management viewset."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "customers.view_customer"
    serializer_class = CustomerSerializer

    def get_queryset(self) -> Customer:
        """Return customers scoped to the request tenant."""
        return Customer.objects.for_tenant(self.request.tenant)

    def create(self, request: Request) -> Response:
        """Create a new customer."""
        self.required_permission = "customers.create_customer"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = serializer.save(tenant=request.tenant)
        return Response(
            CustomerSerializer(customer).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a customer."""
        self.required_permission = "customers.edit_customer"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a customer."""
        self.required_permission = "customers.edit_customer"
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=["get", "put", "patch"], url_path="health-profile")
    def health_profile(self, request: Request, pk: int) -> Response:
        """Retrieve or update the customer's health profile."""
        self.required_permission = "customers.view_customer"
        customer = get_object_or_404(
            Customer.objects.for_tenant(request.tenant),
            id=pk,
        )

        if request.method == "GET":
            try:
                profile = customer.health_profile
            except HealthProfile.DoesNotExist:
                return Response(
                    {"detail": "Health profile not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(HealthProfileSerializer(profile).data)

        self.required_permission = "customers.edit_customer"
        serializer = HealthProfileSerializer(
            data=request.data,
            partial=request.method == "PATCH",
        )
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        defaults = {
            "height_cm": validated.get("height_cm"),
            "weight_kg": validated.get("weight_kg"),
        }
        if request.method == "PATCH" and not hasattr(customer, "health_profile"):
            defaults = {k: v for k, v in defaults.items() if v is not None}
            if not defaults:
                return Response(
                    {"detail": "Health profile does not exist; provide height and weight."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        profile, _ = HealthProfile.objects.get_or_create(
            tenant=request.tenant,
            customer=customer,
            defaults=defaults,
        )
        serializer.instance = profile
        serializer.save(tenant=request.tenant)
        return Response(serializer.data)

    @action(detail=True, methods=["get", "post"])
    def measurements(self, request: Request, pk: int) -> Response:
        """List or create body measurements for a customer."""
        self.required_permission = "customers.view_customer"
        customer = get_object_or_404(
            Customer.objects.for_tenant(request.tenant),
            id=pk,
        )

        if request.method == "GET":
            measurements = customer.body_measurements.all()
            return Response(
                BodyMeasurementSerializer(measurements, many=True).data,
            )

        self.required_permission = "customers.edit_customer"
        serializer = BodyMeasurementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        measurement = serializer.save(
            tenant=request.tenant,
            customer=customer,
        )
        return Response(
            BodyMeasurementSerializer(measurement).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post"], url_path="fitness-goals")
    def fitness_goals(self, request: Request, pk: int) -> Response:
        """List or create fitness goals for a customer."""
        self.required_permission = "customers.view_customer"
        customer = get_object_or_404(
            Customer.objects.for_tenant(request.tenant),
            id=pk,
        )

        if request.method == "GET":
            goals = customer.fitness_goals.all()
            return Response(FitnessGoalSerializer(goals, many=True).data)

        self.required_permission = "customers.edit_customer"
        serializer = FitnessGoalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        goal = serializer.save(tenant=request.tenant, customer=customer)
        return Response(
            FitnessGoalSerializer(goal).data,
            status=status.HTTP_201_CREATED,
        )


class HealthProfileViewSet(ModelViewSet):
    """Direct health profile CRUD viewset."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "customers.view_customer"
    serializer_class = HealthProfileSerializer

    def get_queryset(self) -> HealthProfile:
        """Return health profiles scoped to the request tenant."""
        return HealthProfile.objects.for_tenant(self.request.tenant)

    def create(self, request: Request) -> Response:
        """Create a new health profile."""
        self.required_permission = "customers.edit_customer"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save(tenant=request.tenant)
        return Response(
            HealthProfileSerializer(profile).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a health profile."""
        self.required_permission = "customers.edit_customer"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a health profile."""
        self.required_permission = "customers.edit_customer"
        return super().partial_update(request, *args, **kwargs)


class FitnessGoalViewSet(ModelViewSet):
    """Direct fitness goal CRUD viewset."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "customers.view_customer"
    serializer_class = FitnessGoalSerializer

    def get_queryset(self) -> FitnessGoal:
        """Return fitness goals scoped to the request tenant."""
        return FitnessGoal.objects.for_tenant(self.request.tenant)

    def create(self, request: Request) -> Response:
        """Create a new fitness goal."""
        self.required_permission = "customers.edit_customer"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        goal = serializer.save(tenant=request.tenant)
        return Response(
            FitnessGoalSerializer(goal).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a fitness goal."""
        self.required_permission = "customers.edit_customer"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a fitness goal."""
        self.required_permission = "customers.edit_customer"
        return super().partial_update(request, *args, **kwargs)


class BodyMeasurementViewSet(ModelViewSet):
    """Direct body measurement CRUD viewset."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "customers.view_customer"
    serializer_class = BodyMeasurementSerializer

    def get_queryset(self) -> BodyMeasurement:
        """Return body measurements scoped to the request tenant."""
        return BodyMeasurement.objects.for_tenant(self.request.tenant)

    def create(self, request: Request) -> Response:
        """Create a new body measurement."""
        self.required_permission = "customers.edit_customer"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        measurement = serializer.save(tenant=request.tenant)
        return Response(
            BodyMeasurementSerializer(measurement).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a body measurement."""
        self.required_permission = "customers.edit_customer"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a body measurement."""
        self.required_permission = "customers.edit_customer"
        return super().partial_update(request, *args, **kwargs)
