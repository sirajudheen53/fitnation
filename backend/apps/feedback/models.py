"""Customer feedback models (FBOS-015).

These models let customers submit feedback about their gym experience and
let owners/trainers respond, while also supporting structured surveys with
multiple questions. All entities are tenant-scoped via ``TenantModelMixin``.
"""

from django.db import models

from apps.customers.models import Customer
from apps.tenants.models import TenantModelMixin
from apps.users.models import User


class Feedback(TenantModelMixin):
    """A customer's feedback submission, optionally linked to a survey."""

    class Category(models.TextChoices):
        """Areas a customer can give feedback about."""

        WORKOUT = "workout", "Workout"
        DIET = "diet", "Diet"
        TRAINER = "trainer", "Trainer"
        FACILITY = "facility", "Facility"
        APP = "app", "App"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    rating = models.PositiveSmallIntegerField(
        help_text="Rating between 1 and 5 inclusive.",
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.WORKOUT,
    )
    comment = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=False)
    response = models.TextField(null=True, blank=True)
    response_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedback_responses",
    )
    response_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Feedback model metadata."""

        db_table = "feedback"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="ck_feedback_rating_range",
            ),
        ]

    def __str__(self) -> str:
        """Return a human-readable feedback label."""
        return f"Feedback ({self.rating}/5) by {self.customer.name}"


class FeedbackSurvey(TenantModelMixin):
    """A reusable survey composed of a list of questions."""

    class QuestionType(models.TextChoices):
        """Supported question answer types."""

        RATING = "rating", "Rating"
        TEXT = "text", "Text"
        CHOICE = "choice", "Choice"

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    questions = models.JSONField(
        default=list,
        blank=True,
        help_text=("Array of {question_text, question_type: rating|text|choice, " "choices: [..]} objects."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """FeedbackSurvey model metadata."""

        db_table = "feedback_surveys"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return a human-readable survey label."""
        return f"Survey: {self.name}"


class FeedbackResponse(TenantModelMixin):
    """A customer's submitted answers to a survey."""

    survey = models.ForeignKey(
        FeedbackSurvey,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="survey_responses",
    )
    answers = models.JSONField(default=dict, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """FeedbackResponse model metadata."""

        db_table = "feedback_responses"
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        """Return a human-readable response label."""
        return f"Response to {self.survey.name} by {self.customer.name}"
