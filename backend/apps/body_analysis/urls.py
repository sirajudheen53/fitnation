"""Body analysis app URL configuration."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.body_analysis.views import (
    BodyAnalysisViewSet,
    BodyPhotoUploadViewSet,
    BodyProgressLogViewSet,
)

router = DefaultRouter()
router.register(r"body-analysis", BodyAnalysisViewSet, basename="body-analysis")
router.register(r"body-photo", BodyPhotoUploadViewSet, basename="body-photo")
router.register(r"body-progress", BodyProgressLogViewSet, basename="body-progress")

urlpatterns = [
    # Multipart photo upload lives at POST /api/v1/ai/body-photo/upload/
    path(
        "body-photo/upload/",
        BodyPhotoUploadViewSet.as_view({"post": "create"}),
        name="body-photo-upload",
    ),
    path("", include(router.urls)),
]
