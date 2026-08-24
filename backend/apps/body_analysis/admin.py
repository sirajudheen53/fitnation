"""Body analysis admin configuration."""

from django.contrib import admin

from apps.body_analysis.models import BodyAnalysis, BodyPhoto, BodyProgressLog


class BodyPhotoInline(admin.TabularInline):
    """Inline editing of photos belonging to an analysis."""

    model = BodyPhoto
    extra = 0


@admin.register(BodyAnalysis)
class BodyAnalysisAdmin(admin.ModelAdmin):
    """Admin for body analysis sessions."""

    list_display = (
        "id",
        "uuid",
        "user",
        "tenant",
        "analysis_date",
        "bmi",
        "body_fat_pct",
        "photo_count",
        "created_at",
    )
    list_filter = ("analysis_date",)
    search_fields = ("uuid", "user__email", "notes")
    inlines = [BodyPhotoInline]
    readonly_fields = ("uuid", "bmi", "created_at", "updated_at")


@admin.register(BodyPhoto)
class BodyPhotoAdmin(admin.ModelAdmin):
    """Admin for body photos."""

    list_display = (
        "id",
        "analysis",
        "photo_type",
        "image_url",
        "is_processed",
        "uploaded_at",
    )
    list_filter = ("photo_type", "is_processed")
    search_fields = ("analysis__uuid", "image_url")


@admin.register(BodyProgressLog)
class BodyProgressLogAdmin(admin.ModelAdmin):
    """Admin for body progress logs."""

    list_display = (
        "id",
        "user",
        "tenant",
        "date",
        "metric_type",
        "value",
        "unit",
        "created_at",
    )
    list_filter = ("metric_type", "date")
    search_fields = ("user__email", "notes")
