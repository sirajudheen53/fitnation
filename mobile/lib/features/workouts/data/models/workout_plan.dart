import 'workout_exercise.dart';

/// A workout day within a plan, containing exercises.
class WorkoutDay {
  final int? id;
  final String name;
  final String? description;
  final int? dayNumber;
  final List<WorkoutExercise> exercises;

  const WorkoutDay({
    this.id,
    required this.name,
    this.description,
    this.dayNumber,
    this.exercises = const [],
  });

  factory WorkoutDay.fromJson(Map<String, dynamic> json) {
    return WorkoutDay(
      id: json['id'] as int?,
      name: json['name'] as String? ?? 'Workout Day',
      description: json['description'] as String?,
      dayNumber: json['day_number'] as int?,
      exercises: (json['exercises'] as List<dynamic>?)
              ?.map((e) => WorkoutExercise.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        'name': name,
        if (description != null) 'description': description,
        if (dayNumber != null) 'day_number': dayNumber,
        'exercises': exercises.map((e) => e.toJson()).toList(),
      };
}

/// A workout plan with its days.
class WorkoutPlan {
  final int id;
  final String name;
  final String? description;
  final String? difficulty;
  final int? durationWeeks;
  final int? sessionsPerWeek;
  final List<WorkoutDay> days;

  const WorkoutPlan({
    required this.id,
    required this.name,
    this.description,
    this.difficulty,
    this.durationWeeks,
    this.sessionsPerWeek,
    this.days = const [],
  });

  factory WorkoutPlan.fromJson(Map<String, dynamic> json) {
    return WorkoutPlan(
      id: json['id'] as int,
      name: json['name'] as String? ?? 'Workout Plan',
      description: json['description'] as String?,
      difficulty: json['difficulty'] as String?,
      durationWeeks: json['duration_weeks'] as int?,
      sessionsPerWeek: json['sessions_per_week'] as int?,
      days: (json['days'] as List<dynamic>?)
              ?.map((e) => WorkoutDay.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        if (description != null) 'description': description,
        if (difficulty != null) 'difficulty': difficulty,
        if (durationWeeks != null) 'duration_weeks': durationWeeks,
        if (sessionsPerWeek != null) 'sessions_per_week': sessionsPerWeek,
        'days': days.map((e) => e.toJson()).toList(),
      };
}

/// A workout assignment linking a customer to a plan.
class WorkoutAssignment {
  final int id;
  final int customerId;
  final int planId;
  final String? planName;
  final bool isActive;
  final DateTime? assignedAt;
  final DateTime? startDate;
  final DateTime? endDate;

  const WorkoutAssignment({
    required this.id,
    required this.customerId,
    required this.planId,
    this.planName,
    this.isActive = true,
    this.assignedAt,
    this.startDate,
    this.endDate,
  });

  factory WorkoutAssignment.fromJson(Map<String, dynamic> json) {
    return WorkoutAssignment(
      id: json['id'] as int,
      customerId: json['customer'] as int? ?? json['customer_id'] as int? ?? 0,
      planId: json['plan'] as int? ?? json['plan_id'] as int? ?? 0,
      planName: json['plan_name'] as String?,
      isActive: (json['is_active'] as bool?) ?? true,
      assignedAt: json['assigned_at'] != null
          ? DateTime.tryParse(json['assigned_at'].toString())
          : null,
      startDate: json['start_date'] != null
          ? DateTime.tryParse(json['start_date'].toString())
          : null,
      endDate: json['end_date'] != null
          ? DateTime.tryParse(json['end_date'].toString())
          : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'customer': customerId,
        'plan': planId,
        if (planName != null) 'plan_name': planName,
        'is_active': isActive,
      };
}
