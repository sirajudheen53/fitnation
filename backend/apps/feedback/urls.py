"""Feedback app URL configuration (FBOS-015)."""

from rest_framework.routers import DefaultRouter

from apps.feedback.views import (
    FeedbackAnalyticsViewSet,
    FeedbackResponseViewSet,
    FeedbackSurveyViewSet,
    FeedbackViewSet,
)

router = DefaultRouter()
router.register(r"feedback", FeedbackViewSet, basename="feedback")
router.register(
    r"feedback-analytics",
    FeedbackAnalyticsViewSet,
    basename="feedback-analytics",
)
router.register(
    r"feedback-surveys",
    FeedbackSurveyViewSet,
    basename="feedback-survey",
)
router.register(
    r"feedback-responses",
    FeedbackResponseViewSet,
    basename="feedback-response",
)

urlpatterns = router.urls
