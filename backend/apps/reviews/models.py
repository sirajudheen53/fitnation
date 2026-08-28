"""Customer reviews & ratings models (FBOS-034).

Customers leave a star rating (1-5) and optional text review for a branch.
Staff (owners/managers/trainers) can post a single response to each review.
All entities are tenant-scoped via ``TenantModelMixin``.
"""

from django.db import models

from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.tenants.models import TenantModelMixin
from apps.users.models import User


class Review(TenantModelMixin):
    """A customer's star rating and review for a branch."""

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(
        help_text="Rating between 1 and 5 inclusive.",
    )
    text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Review model metadata."""

        db_table = "reviews"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="ck_review_rating_range",
            ),
        ]

    def __str__(self) -> str:
        """Return a human-readable review label."""
        return f"Review ({self.rating}/5) by {self.customer.name}"


class ReviewResponse(TenantModelMixin):
    """A staff member's response to a customer review."""

    review = models.OneToOneField(
        Review,
        on_delete=models.CASCADE,
        related_name="response",
    )
    text = models.TextField()
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_responses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """ReviewResponse model metadata."""

        db_table = "review_responses"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return a human-readable response label."""
        return f"Response to review #{self.review_id}"
