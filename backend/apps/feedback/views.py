"""Feedback API views (FBOS-015).

Endpoints:
- ``/feedback/`` — customer feedback CRUD + response by trainers/owners.
- ``/feedback-analytics/`` — aggregate analytics for a tenant.
- ``/feedback-surveys/`` — survey CRUD + submit response.
- ``/feedback-responses/`` — survey responses view.
"""

from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.customers.models import Customer
from apps.feedback.models import Feedback, FeedbackResponse, FeedbackSurvey
from apps.feedback.serializers import (
    FeedbackSerializer,
    FeedbackSurveyResponseSerializer,
    FeedbackSurveySerializer,
    FeedbackWriteSerializer,
)
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication
from apps.users.models import User


class FeedbackObjectPermission(RolePermission):
    """Object-level access for feedback survey objects.

    Surveys and survey responses are shared/collective records rather than a
    single customer's private data. Customers may access surveys (to view and
    submit) and their own responses; the response queryset is already scoped to
    the requesting customer, so object access for customers is safe.
    """

    def has_object_permission(self, request, view, obj):
        """Enforce tenant scoping but relax the customer-ownership rule for surveys."""
        if not request.user.is_authenticated or request.user.is_superuser:
            return True
        if (
            hasattr(obj, "tenant_id")
            and obj.tenant_id is not None
            and obj.tenant_id != request.user.tenant_id
        ):
            return False
        if request.user.role == "customer":
            return isinstance(obj, (FeedbackSurvey, FeedbackResponse))
        return True


class FeedbackViewSet(viewsets.ModelViewSet):
    """Tenant-scoped customer feedback management.

    Customers may submit feedback and view their own records. Trainers, managers,
    and owners may view all feedback for the tenant and post responses.
    """

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "feedback.view_feedback"
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_permissions(self):
        """Set the action-appropriate required permission before evaluating access.

        ``required_permission`` must be set before ``initial()`` calls
        ``has_permission``, so we resolve it here based on the HTTP method.
        """
        self.required_permission = {
            "POST": "feedback.create_feedback" if self.action == "create" else "feedback.edit_feedback",
            "PUT": "feedback.edit_feedback",
            "PATCH": "feedback.edit_feedback",
        }.get(self.request.method, "feedback.view_feedback")
        return super().get_permissions()

    def get_serializer_class(self):
        """Use the write serializer for create/update; read serializer otherwise."""
        if self.action in ("create", "update", "partial_update"):
            return FeedbackWriteSerializer
        return FeedbackSerializer

    def get_queryset(self):
        """Return feedback scoped to the tenant.

        Customers only see their own feedback; staff roles see all tenant feedback.
        """
        queryset = Feedback.objects.for_tenant(self.request.tenant).select_related(
            "customer", "response_by"
        )
        if self.request.user.role == User.Role.CUSTOMER:
            queryset = queryset.filter(
                customer__user=self.request.user
            )
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category=category)
        return queryset

    def perform_create(self, serializer):
        """Persist feedback scoped to the tenant and the requesting customer."""
        customer = None
        if self.request.user.role == User.Role.CUSTOMER:
            customer = Customer.objects.filter(
                tenant=self.request.tenant, user=self.request.user
            ).first()
        elif self.request.data.get("customer"):
            customer = Customer.objects.filter(
                tenant=self.request.tenant, id=self.request.data["customer"]
            ).first()
        serializer.save(tenant=self.request.tenant, customer=customer)

    def update(self, request, *args, **kwargs):
        """Trainers/owners may edit feedback; customers may only edit their own."""
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Allow partial edits."""
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="respond")
    def respond(self, request: Request, pk: int) -> Response:
        """Allow a trainer/manager/owner to post a response to feedback."""
        self.required_permission = "feedback.edit_feedback"
        feedback = self.get_object()
        response_text = request.data.get("response")
        if not response_text:
            return Response(
                {"response": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        feedback.response = response_text
        feedback.response_by = request.user
        feedback.response_at = timezone.now()
        feedback.save(update_fields=["response", "response_by", "response_at", "updated_at"])
        return Response(FeedbackSerializer(feedback).data)


class FeedbackAnalyticsViewSet(viewsets.GenericViewSet):
    """Read-only analytics for customer feedback within a tenant."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "feedback.view_feedback"
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        """Return all feedback for the tenant."""
        return Feedback.objects.for_tenant(self.request.tenant)

    def list(self, request: Request) -> Response:
        """Return aggregate feedback analytics for the tenant."""
        queryset = self.get_queryset()

        total = queryset.count()
        distribution = list(
            queryset.values("rating").annotate(count=Count("id")).order_by("rating")
        )
        rating_counts = {row["rating"]: row["count"] for row in distribution}
        distribution = [
            {"rating": r, "count": rating_counts.get(r, 0)} for r in range(1, 6)
        ]

        category_breakdown = list(
            queryset.values("category").annotate(count=Count("id")).order_by("category")
        )
        average_rating = queryset.aggregate(avg=Avg("rating"))["avg"]

        # Sentiment summary based on the rating scale.
        ratings = list(queryset.values_list("rating", flat=True))
        positive = sum(1 for r in ratings if r >= 4)
        neutral = sum(1 for r in ratings if r == 3)
        negative = sum(1 for r in ratings if r <= 2)
        sentiment = {
            "positive": positive,
            "neutral": neutral,
            "negative": negative,
            "positive_pct": round((positive / total * 100), 1) if total else 0,
            "neutral_pct": round((neutral / total * 100), 1) if total else 0,
            "negative_pct": round((negative / total * 100), 1) if total else 0,
        }

        # Trend over time: group feedback by day (last 30 days by default).
        days = int(request.query_params.get("days", 30))
        trend = []
        start = timezone.now().date() - timedelta(days=days - 1)
        recent = queryset.filter(created_at__date__gte=start)
        day_counts = {
            row["day"]: row["count"]
            for row in recent.extra(select={"day": "date(created_at)"})
            .values("day")
            .annotate(count=Count("id"))
        }
        for offset in range(days):
            day = start + timedelta(days=offset)
            trend.append(
                {
                    "date": day.isoformat(),
                    "count": day_counts.get(day, 0),
                }
            )

        return Response(
            {
                "total_feedback": total,
                "average_rating": round(float(average_rating), 2) if average_rating else None,
                "rating_distribution": distribution,
                "category_breakdown": category_breakdown,
                "sentiment_summary": sentiment,
                "trend": trend,
            }
        )


class FeedbackSurveyViewSet(viewsets.ModelViewSet):
    """CRUD for feedback surveys plus a submit-response action."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, FeedbackObjectPermission]
    required_permission = "feedback.view_feedback"
    serializer_class = FeedbackSurveySerializer
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_permissions(self):
        """Set the action-appropriate required permission before access is evaluated."""
        if self.action == "submit":
            self.required_permission = "feedback.create_feedback"
        elif self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            self.required_permission = "feedback.edit_feedback"
        else:
            self.required_permission = "feedback.view_feedback"
        return super().get_permissions()

    def get_queryset(self):
        """Return surveys scoped to the tenant."""
        return FeedbackSurvey.objects.for_tenant(self.request.tenant)

    def create(self, request: Request) -> Response:
        """Create a new survey (staff only)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        survey = serializer.save(tenant=request.tenant)
        return Response(
            FeedbackSurveySerializer(survey).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        """Update a survey (staff only)."""
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Partially update a survey (staff only)."""
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete a survey (staff only)."""
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request: Request, pk: int) -> Response:
        """Submit a response to a survey as the requesting customer."""
        survey = self.get_object()
        if not survey.is_active:
            return Response(
                {"detail": "This survey is not active."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        customer = Customer.objects.filter(
            tenant=self.request.tenant, user=self.request.user
        ).first()
        if customer is None:
            return Response(
                {"detail": "Customer profile required to submit a survey response."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = FeedbackResponse.objects.create(
            tenant=self.request.tenant,
            survey=survey,
            customer=customer,
            answers=request.data.get("answers", {}),
        )
        return Response(
            FeedbackSurveyResponseSerializer(response).data,
            status=status.HTTP_201_CREATED,
        )


class FeedbackResponseViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only listing of survey responses within a tenant."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, FeedbackObjectPermission]
    required_permission = "feedback.view_feedback"
    serializer_class = FeedbackSurveyResponseSerializer
    http_method_names = ["get", "head", "options"]
    filterset_fields = ["survey"]

    def get_queryset(self):
        """Return responses scoped to the tenant."""
        queryset = FeedbackResponse.objects.for_tenant(self.request.tenant).select_related(
            "survey", "customer"
        )
        if self.request.user.role == User.Role.CUSTOMER:
            queryset = queryset.filter(customer__user=self.request.user)
        return queryset



