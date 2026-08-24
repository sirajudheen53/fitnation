import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_card.dart';
import '../../data/models/workout_plan.dart';

/// Shows the details of a workout day with its exercises.
class WorkoutDetailScreen extends StatelessWidget {
  final WorkoutPlan plan;
  final WorkoutDay day;

  const WorkoutDetailScreen({
    super.key,
    required this.plan,
    required this.day,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(day.name)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (day.description != null) ...[
            Text(
              day.description!,
              style: const TextStyle(color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 16),
          ],
          for (final we in day.exercises) _ExerciseCard(workoutExercise: we),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: () => context.push(
              '/workouts/log',
              extra: {'plan': plan, 'day': day},
            ),
            icon: const Icon(Icons.check_circle_outline),
            label: const Text('Log This Workout'),
          ),
        ],
      ),
    );
  }
}

class _ExerciseCard extends StatelessWidget {
  final WorkoutExercise workoutExercise;

  const _ExerciseCard({required this.workoutExercise});

  @override
  Widget build(BuildContext context) {
    final exercise = workoutExercise.exercise;
    final targetSets = workoutExercise.targetSets;
    final targetReps = workoutExercise.targetReps;

    return AppCard(
      margin: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: AppTheme.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.fitness_center, color: AppTheme.primary),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      exercise.name,
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                    ),
                    if (exercise.muscleGroup != null)
                      Text(
                        exercise.muscleGroup!,
                        style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                      ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Target sets/reps
          Row(
            children: [
              _Chip(icon: Icons.repeat, label: '$targetSets sets'),
              const SizedBox(width: 8),
              _Chip(icon: Icons.exposure, label: '$targetReps reps'),
              if (workoutExercise.restSeconds != null) ...[
                const SizedBox(width: 8),
                _Chip(icon: Icons.timer, label: '${workoutExercise.restSeconds}s rest'),
              ],
            ],
          ),
          if (exercise.instructions.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              'Instructions',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 4),
            for (final (i, instruction) in exercise.instructions.indexed)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(
                  '${i + 1}. $instruction',
                  style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                ),
              ),
          ],
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _Chip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppTheme.background,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: AppTheme.primary),
          const SizedBox(width: 4),
          Text(label, style: const TextStyle(fontSize: 12)),
        ],
      ),
    );
  }
}
