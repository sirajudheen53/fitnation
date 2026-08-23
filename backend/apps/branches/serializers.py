"""Branch serializers."""

from rest_framework import serializers

from apps.branches.models import Branch


class BranchSerializer(serializers.ModelSerializer):
    """Serialize branch details."""

    class Meta:
        """Serializer metadata."""

        model = Branch
        fields = [
            "id",
            "uuid",
            "name",
            "branch_type",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "latitude",
            "longitude",
            "phone",
            "email",
            "opening_time",
            "closing_time",
            "operating_days",
            "is_active",
            "is_headquarters",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "uuid", "created_at", "updated_at"]
