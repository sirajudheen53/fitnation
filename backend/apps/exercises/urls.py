"""Exercises app URL configuration."""

from rest_framework.routers import DefaultRouter

from apps.exercises.views import ExerciseCategoryViewSet, ExerciseViewSet

router = DefaultRouter()
router.register(r"exercise-categories", ExerciseCategoryViewSet, basename="exercise-category")
router.register(r"exercises", ExerciseViewSet, basename="exercise")

urlpatterns = router.urls
