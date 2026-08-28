"""Reviews API views (FBOS-034).

Endpoints:
- ``POST /reviews/`` — create a review (customers).
- ``GET /reviews/?branch_id=`` — list reviews for a branch with aggregate rating.
- ``POST /reviews/{id}/respond/`` — staff respond to a review.
"""

from django.db.models import Avg, Count
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.customers.models import Customer
from apps.permissions.permissions import RolePermission
from apps.reviews.models import Review, ReviewResponse
from apps.reviews.serializers import (
    ReviewResponseSerializer,
    ReviewSerializer,
    ReviewWriteSerializer,
)
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication
from apps.users.models import User


class ReviewViewSet(viewsets.ModelViewSet):
    """Tenant-scoped customer reviews & ratings.

    Customers may submit reviews and view their own records. Staff roles may view
    all reviews for the tenant and post responses.
    """

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "reviews.view_review"
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        """Set the action-appropriate required permission before access is evaluated."""
        if self.action == "create":
            self.required_permission = "reviews.create_review"
        elif self.action == "respond":
            self.required_permission = "reviews.edit_review"
        else:
            self.required_permission = "reviews.view_review"
        return super().get_permissions()

    def get_serializer_class(self):
        """Use the write serializer for create; read serializer otherwise."""
        if self.action == "create":
            return ReviewWriteSerializer
        return ReviewSerializer

    def get_queryset(self):
        """Return reviews scoped to the tenant.

        Customers only see their own reviews; staff roles see all tenant reviews.
        """
        queryset = Review.objects.for_tenant(self.request.tenant).select_related(
            "customer",
            "branch",
            "response",
            "response__author",
        )
        if self.request.user.role == User.Role.CUSTOMER:
            queryset = queryset.filter(customer__user=self.request.user)
        branch_id = self.request.query_params.get("branch_id")
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        return queryset

    def list(self, request: Request, *args, **kwargs) -> Response:
        """List reviews with aggregate rating (average and count)."""
        queryset = self.filter_queryset(self.get_queryset())

        aggregate = queryset.aggregate(
            average_rating=Avg("rating"),
            count=Count("id"),
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(queryset, many=True)
            data = serializer.data

        data["average_rating"] = (
            round(float(aggregate["average_rating"]), 2)
            if aggregate["average_rating"] is not None
            else None
        )
        data["count"] = aggregate["count"]
        return Response(data)

    def perform_create(self, serializer):
        """Persist a review scoped to the tenant and the requesting customer."""
        customer = None
        if self.request.user.role == User.Role.CUSTOMER:
            customer = Customer.objects.filter(
                tenant=self.request.tenant,
                user=self.request.user,
            ).first()
        elif self.request.data.get("customer"):
            customer = Customer.objects.filter(
                tenant=self.request.tenant,
                id=self.request.data["customer"],
            ).first()
        serializer.save(tenant=self.request.tenant, customer=customer)

    @action(detail=True, methods=["post"], url_path="respond")
    def respond(self, request: Request, pk: int) -> Response:
        """Allow a staff member to post a response to a review."""
        review = self.get_object()
        text = request.data.get("text")
        if not text:
            return Response(
                {"text": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response, _ = ReviewResponse.objects.update_or_create(
            tenant=self.request.tenant,
            review=review,
            defaults={"text": text, "author": request.user},
        )
        return Response(ReviewResponseSerializer(response).data)
