import 'exercise.dart';

/// A set within an exercise (weight, reps, rest).
class ExerciseSet {
  final int? id;
  final int setNumber;
  final double? weight;
  final int? reps;
  final int? restSeconds;
  final bool isCompleted;

  const ExerciseSet({
    this.id,
    required this.setNumber,
    this.weight,
    this.reps,
    this.restSeconds,
    this.isCompleted = false,
  });

  factory ExerciseSet.fromJson(Map<String, dynamic> json) {
    return ExerciseSet(
      id: json['id'] as int?,
      setNumber: json['set_number'] as int? ?? json['set'] as int? ?? 1,
      weight: (json['weight'] as num?)?.toDouble(),
      reps: json['reps'] as int?,
      restSeconds: json['rest_seconds'] as int?,
      isCompleted: (json['is_completed'] as bool?) ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        'set_number': setNumber,
        if (weight != null) 'weight': weight,
        if (reps != null) 'reps': reps,
        if (restSeconds != null) 'rest_seconds': restSeconds,
        'is_completed': isCompleted,
      };

  ExerciseSet copyWith({
    int? id,
    int? setNumber,
    double? weight,
    int? reps,
    int? restSeconds,
    bool? isCompleted,
  }) {
    return ExerciseSet(
      id: id ?? this.id,
      setNumber: setNumber ?? this.setNumber,
      weight: weight ?? this.weight,
      reps: reps ?? this.reps,
      restSeconds: restSeconds ?? this.restSeconds,
      isCompleted: isCompleted ?? this.isCompleted,
    );
  }
}

/// An exercise within a workout day, with its sets.
class WorkoutExercise {
  final int? id;
  final Exercise exercise;
  final int? order;
  final int? targetSets;
  final int? targetReps;
  final int? restSeconds;
  final List<ExerciseSet> sets;
  final String? notes;

  const WorkoutExercise({
    this.id,
    required this.exercise,
    this.order,
    this.targetSets,
    this.targetReps,
    this.restSeconds,
    this.sets = const [],
    this.notes,
  });

  factory WorkoutExercise.fromJson(Map<String, dynamic> json) {
    final exerciseJson = json['exercise'] as Map<String, dynamic>?;
    return WorkoutExercise(
      id: json['id'] as int?,
      exercise: exerciseJson != null
          ? Exercise.fromJson(exerciseJson)
          : Exercise(id: json['exercise_id'] as int? ?? 0, name: 'Exercise'),
      order: json['order'] as int?,
      targetSets: json['target_sets'] as int?,
      targetReps: json['target_reps'] as int?,
      restSeconds: json['rest_seconds'] as int?,
      sets: (json['sets'] as List<dynamic>?)
              ?.map((e) => ExerciseSet.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      notes: json['notes'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        'exercise': exercise.toJson(),
        if (order != null) 'order': order,
        if (targetSets != null) 'target_sets': targetSets,
        if (targetReps != null) 'target_reps': targetReps,
        if (restSeconds != null) 'rest_seconds': restSeconds,
        'sets': sets.map((e) => e.toJson()).toList(),
        if (notes != null) 'notes': notes,
      };
}
