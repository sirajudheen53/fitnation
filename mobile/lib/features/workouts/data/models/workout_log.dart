/// A logged workout session (completed by the customer).
class WorkoutLog {
  final int? id;
  final int? customerId;
  final int? planId;
  final int? dayId;
  final DateTime? loggedAt;
  final int? durationMinutes;
  final int? caloriesBurned;
  final String? notes;
  final List<LoggedSet> sets;

  const WorkoutLog({
    this.id,
    this.customerId,
    this.planId,
    this.dayId,
    this.loggedAt,
    this.durationMinutes,
    this.caloriesBurned,
    this.notes,
    this.sets = const [],
  });

  factory WorkoutLog.fromJson(Map<String, dynamic> json) {
    return WorkoutLog(
      id: json['id'] as int?,
      customerId: json['customer'] as int? ?? json['customer_id'] as int?,
      planId: json['plan'] as int? ?? json['plan_id'] as int?,
      dayId: json['day'] as int? ?? json['day_id'] as int?,
      loggedAt: json['logged_at'] != null
          ? DateTime.tryParse(json['logged_at'].toString())
          : null,
      durationMinutes: json['duration_minutes'] as int?,
      caloriesBurned: json['calories_burned'] as int?,
      notes: json['notes'] as String?,
      sets: (json['sets'] as List<dynamic>?)
              ?.map((e) => LoggedSet.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        if (customerId != null) 'customer': customerId,
        if (planId != null) 'plan': planId,
        if (dayId != null) 'day': dayId,
        if (loggedAt != null) 'logged_at': loggedAt!.toIso8601String(),
        if (durationMinutes != null) 'duration_minutes': durationMinutes,
        if (caloriesBurned != null) 'calories_burned': caloriesBurned,
        if (notes != null) 'notes': notes,
        'sets': sets.map((e) => e.toJson()).toList(),
      };
}

/// A single logged set within a workout log.
class LoggedSet {
  final int? exerciseId;
  final int setNumber;
  final double? weight;
  final int? reps;
  final int? restSeconds;
  final bool isCompleted;

  const LoggedSet({
    this.exerciseId,
    required this.setNumber,
    this.weight,
    this.reps,
    this.restSeconds,
    this.isCompleted = true,
  });

  factory LoggedSet.fromJson(Map<String, dynamic> json) {
    return LoggedSet(
      exerciseId: json['exercise'] as int? ?? json['exercise_id'] as int?,
      setNumber: json['set_number'] as int? ?? 1,
      weight: (json['weight'] as num?)?.toDouble(),
      reps: json['reps'] as int?,
      restSeconds: json['rest_seconds'] as int?,
      isCompleted: (json['is_completed'] as bool?) ?? true,
    );
  }

  Map<String, dynamic> toJson() => {
        if (exerciseId != null) 'exercise': exerciseId,
        'set_number': setNumber,
        if (weight != null) 'weight': weight,
        if (reps != null) 'reps': reps,
        if (restSeconds != null) 'rest_seconds': restSeconds,
        'is_completed': isCompleted,
      };
}
