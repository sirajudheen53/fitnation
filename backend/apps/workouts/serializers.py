"""Workout Builder serializers."""

from rest_framework import serializers

from apps.exercises.models import Exercise
from apps.exercises.serializers import ExerciseSerializer
from apps.workouts.models import (
    WorkoutAssignment,
    WorkoutDay,
    WorkoutExercise,
    WorkoutLog,
    WorkoutPlan,
)


class WorkoutExerciseSerializer(serializers.ModelSerializer):
    """Serialize a workout exercise with inline exercise details."""

    exercise_name = serializers.CharField(
        source="exercise.name",
        read_only=True,
    )
    exercise_details = ExerciseSerializer(
        source="exercise",
        read_only=True,
    )
    alternate_exercise_name = serializers.CharField(
        source="alternate_exercise.name",
        read_only=True,
    )

    class Meta:
        """Serializer metadata."""

        model = WorkoutExercise
        fields = [
            "id",
            "workout_day",
            "exercise",
            "exercise_name",
            "exercise_details",
            "sets",
            "reps",
            "rest_seconds",
            "tempo",
            "rpe",
            "notes",
            "order",
            "alternate_exercise",
            "alternate_exercise_name",
        ]
        read_only_fields = ["id", "exercise_name", "exercise_details", "alternate_exercise_name"]
        extra_kwargs = {"workout_day": {"required": False}}

    def validate_exercise(self, value: Exercise) -> Exercise:
        """Ensure the exercise belongs to the request tenant."""
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "The exercise does not belong to the current tenant.",
            )
        return value

    def validate_alternate_exercise(self, value: Exercise | None) -> Exercise | None:
        """Ensure the alternate exercise belongs to the request tenant."""
        if value is None:
            return value
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "The alternate exercise does not belong to the current tenant.",
            )
        return value

    def validate_rpe(self, value: int | None) -> int | None:
        """Ensure RPE is within the 1-10 scale."""
        if value is not None and not (1 <= value <= 10):
            raise serializers.ValidationError("RPE must be between 1 and 10.")
        return value

    def create(self, validated_data: dict) -> WorkoutExercise:
        """Create a workout exercise, injecting the parent day and tenant."""
        workout_day = validated_data.pop("workout_day", None)
        if workout_day is None:
            workout_day = self.context["workout_day"]
        return WorkoutExercise.objects.create(
            workout_day=workout_day,
            tenant=workout_day.tenant,
            **validated_data,
        )


class WorkoutExerciseNestedSerializer(WorkoutExerciseSerializer):
    """WorkoutExercise serializer used for nested (read) representation."""

    class Meta(WorkoutExerciseSerializer.Meta):
        extra_kwargs = {
            "exercise": {"required": True},
            "workout_day": {"required": False},
        }


class WorkoutDaySerializer(serializers.ModelSerializer):
    """Serialize a workout day with nested exercises."""

    exercises = WorkoutExerciseSerializer(many=True, required=False)

    class Meta:
        """Serializer metadata."""

        model = WorkoutDay
        fields = [
            "id",
            "workout_plan",
            "day_of_week",
            "day_number",
            "focus",
            "notes",
            "exercises",
        ]
        read_only_fields = ["id", "workout_plan"]

    def create(self, validated_data: dict) -> WorkoutDay:
        """Create a day and its nested exercises."""
        exercises_data = validated_data.pop("exercises", [])
        workout_plan = validated_data.pop("workout_plan", None)
        if workout_plan is None:
            workout_plan = self.context["workout_plan"]
        day = WorkoutDay.objects.create(
            workout_plan=workout_plan,
            tenant=workout_plan.tenant,
            **validated_data,
        )
        for exercise_data in exercises_data:
            WorkoutExercise.objects.create(
                tenant=workout_plan.tenant,
                workout_day=day,
                **exercise_data,
            )
        return day

    def update(self, instance: WorkoutDay, validated_data: dict) -> WorkoutDay:
        """Update a workout day, supporting full nested exercises replacement."""
        exercises_data = validated_data.pop("exercises", None)
        instance = super().update(instance, validated_data)

        if exercises_data is not None:
            instance.exercises.all().delete()
            for exercise_data in exercises_data:
                WorkoutExercise.objects.create(
                    tenant=instance.tenant,
                    workout_day=instance,
                    **exercise_data,
                )

        return instance


class WorkoutDayWriteSerializer(WorkoutDaySerializer):
    """Writable workout day used for nested CRUD via the day viewset."""

    workout_plan = serializers.PrimaryKeyRelatedField(
        queryset=WorkoutPlan.objects.all(),
        required=True,
    )

    class Meta(WorkoutDaySerializer.Meta):
        read_only_fields = ["id"]


class WorkoutPlanSerializer(serializers.ModelSerializer):
    """Serialize a workout plan with nested days and exercises."""

    days = WorkoutDaySerializer(many=True, required=False)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name",
        read_only=True,
    )

    class Meta:
        """Serializer metadata."""

        model = WorkoutPlan
        fields = [
            "id",
            "name",
            "description",
            "goal",
            "difficulty",
            "duration_weeks",
            "is_template",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
            "days",
        ]
        read_only_fields = ["id", "created_by", "created_by_name", "created_at", "updated_at"]

    def create(self, validated_data: dict) -> WorkoutPlan:
        """Create a workout plan with nested days and exercises in one request."""
        days_data = validated_data.pop("days", [])
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)
        created_by = getattr(request, "user", None)
        plan = WorkoutPlan.objects.create(
            tenant=tenant,
            created_by=created_by,
            **validated_data,
        )
        for day_data in days_data:
            exercises_data = day_data.pop("exercises", [])
            day = WorkoutDay.objects.create(
                workout_plan=plan,
                tenant=plan.tenant,
                **day_data,
            )
            for exercise_data in exercises_data:
                WorkoutExercise.objects.create(
                    workout_day=day,
                    tenant=plan.tenant,
                    **exercise_data,
                )
        return plan

    def update(self, instance: WorkoutPlan, validated_data: dict) -> WorkoutPlan:
        """Update a workout plan, supporting full nested days replacement."""
        days_data = validated_data.pop("days", None)
        instance = super().update(instance, validated_data)

        if days_data is not None:
            instance.days.all().delete()
            for day_data in days_data:
                exercises_data = day_data.pop("exercises", [])
                day = WorkoutDay.objects.create(
                    workout_plan=instance,
                    tenant=instance.tenant,
                    **day_data,
                )
                for exercise_data in exercises_data:
                    WorkoutExercise.objects.create(
                        workout_day=day,
                        tenant=instance.tenant,
                        **exercise_data,
                    )

        return instance


class WorkoutAssignmentSerializer(serializers.ModelSerializer):
    """Serialize a workout plan assignment to a customer."""

    workout_plan_name = serializers.CharField(
        source="workout_plan.name",
        read_only=True,
    )
    customer_name = serializers.CharField(
        source="customer.name",
        read_only=True,
    )

    class Meta:
        """Serializer metadata."""

        model = WorkoutAssignment
        fields = [
            "id",
            "customer",
            "workout_plan",
            "workout_plan_name",
            "customer_name",
            "start_date",
            "end_date",
            "is_active",
            "assigned_by",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "assigned_by", "created_at", "updated_at"]

    def validate_customer(self, value) -> object:
        """Ensure the customer belongs to the request tenant."""
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "The customer does not belong to the current tenant.",
            )
        return value

    def validate_workout_plan(self, value: WorkoutPlan) -> WorkoutPlan:
        """Ensure the workout plan belongs to the request tenant."""
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "The workout plan does not belong to the current tenant.",
            )
        return value


class WorkoutLogSerializer(serializers.ModelSerializer):
    """Serialize a logged workout set."""

    exercise_name = serializers.CharField(
        source="workout_exercise.exercise.name",
        read_only=True,
    )
    customer_name = serializers.CharField(
        source="customer.name",
        read_only=True,
    )

    class Meta:
        """Serializer metadata."""

        model = WorkoutLog
        fields = [
            "id",
            "customer",
            "workout_exercise",
            "workout_day",
            "exercise_name",
            "customer_name",
            "date_completed",
            "set_number",
            "actual_reps",
            "actual_weight",
            "actual_rest_seconds",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "exercise_name", "customer_name", "created_at"]

    def validate_customer(self, value) -> object:
        """Ensure the customer belongs to the request tenant."""
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "The customer does not belong to the current tenant.",
            )
        return value

    def validate_workout_exercise(self, value: WorkoutExercise) -> WorkoutExercise:
        """Ensure the workout exercise belongs to the request tenant."""
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "The workout exercise does not belong to the current tenant.",
            )
        return value

    def validate_workout_day(self, value: WorkoutDay) -> WorkoutDay:
        """Ensure the workout day belongs to the request tenant."""
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "The workout day does not belong to the current tenant.",
            )
        return value
