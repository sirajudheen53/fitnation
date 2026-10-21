import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/workouts/data/models/exercise.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_exercise.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_log.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_plan.dart';

void main() {
  group('Exercise', () {
    test('parses a full exercise and round-trips', () {
      const exercise = Exercise(
        id: 5,
        name: 'Bench Press',
        description: 'Compound push',
        category: 'strength',
        difficulty: 'intermediate',
        muscleGroup: 'chest',
        equipment: 'barbell',
        imageUrl: 'https://cdn.example.com/bench.png',
        videoUrl: 'https://cdn.example.com/bench.mp4',
        instructions: ['Lie flat', 'Lower the bar', 'Press up'],
      );

      final reparsed = Exercise.fromJson(exercise.toJson());
      expect(reparsed.id, 5);
      expect(reparsed.name, 'Bench Press');
      expect(reparsed.muscleGroup, 'chest');
      expect(reparsed.instructions, hasLength(3));
    });

    test('degrades a missing name and tolerates missing instructions', () {
      final parsed = Exercise.fromJson({'id': 1});
      expect(parsed.name, 'Exercise');
      expect(parsed.instructions, isEmpty);
    });
  });

  group('ExerciseSet', () {
    test('parses and round-trips', () {
      const set = ExerciseSet(
        id: 1,
        setNumber: 2,
        weight: 60.5,
        reps: 10,
        restSeconds: 90,
        isCompleted: true,
      );

      final reparsed = ExerciseSet.fromJson(set.toJson());
      expect(reparsed.setNumber, 2);
      expect(reparsed.weight, 60.5);
      expect(reparsed.reps, 10);
      expect(reparsed.isCompleted, isTrue);
    });

    test('set_number accepts the alias set and defaults to 1', () {
      expect(ExerciseSet.fromJson({'set': 3}).setNumber, 3);
      expect(ExerciseSet.fromJson({}).setNumber, 1);
      expect(ExerciseSet.fromJson({}).isCompleted, isFalse);
    });

    test('copyWith overrides only the given fields', () {
      const set = ExerciseSet(setNumber: 1, weight: 40, reps: 8);
      final updated = set.copyWith(reps: 12, isCompleted: true);
      expect(updated.reps, 12);
      expect(updated.weight, 40);
      expect(updated.setNumber, 1);
      expect(updated.isCompleted, isTrue);
      expect(set.copyWith().weight, 40);
    });
  });

  group('WorkoutExercise', () {
    test('parses a nested exercise with sets', () {
      final we = WorkoutExercise.fromJson({
        'id': 1,
        'exercise': {'id': 5, 'name': 'Squat'},
        'order': 1,
        'target_sets': 3,
        'target_reps': 12,
        'rest_seconds': 60,
        'sets': [
          {'set_number': 1, 'reps': 12, 'weight': 50},
        ],
        'notes': 'go deep',
      });

      expect(we.exercise.name, 'Squat');
      expect(we.order, 1);
      expect(we.targetSets, 3);
      expect(we.sets, hasLength(1));
      expect(we.notes, 'go deep');

      final reparsed = WorkoutExercise.fromJson(we.toJson());
      expect(reparsed.exercise.id, 5);
      expect(reparsed.sets, hasLength(1));
    });

    test('falls back to a placeholder exercise when only the id is present', () {
      final we = WorkoutExercise.fromJson({'exercise_id': 9});
      expect(we.exercise.id, 9);
      expect(we.exercise.name, 'Exercise');
      expect(we.sets, isEmpty);
    });
  });

  group('WorkoutLog / LoggedSet', () {
    test('parses canonical and alias keys', () {
      final log = WorkoutLog.fromJson({
        'id': 1,
        'customer_id': 10,
        'plan_id': 20,
        'day': 30,
        'logged_at': '2026-06-05T18:00:00Z',
        'duration_minutes': 45,
        'calories_burned': 320,
        'notes': 'felt strong',
        'sets': [
          {'set_number': 1, 'weight': 60, 'reps': 10},
        ],
      });

      expect(log.customerId, 10);
      expect(log.planId, 20);
      expect(log.dayId, 30);
      expect(log.loggedAt, DateTime.parse('2026-06-05T18:00:00Z'));
      expect(log.durationMinutes, 45);
      expect(log.caloriesBurned, 320);
      expect(log.sets, hasLength(1));

      final reparsed = WorkoutLog.fromJson(log.toJson());
      expect(reparsed.planId, 20);
      expect(reparsed.sets, hasLength(1));
    });

    test('accepts the nested-key aliases (customer/plan/exercise)', () {
      final log = WorkoutLog.fromJson({
        'customer': 7,
        'plan': 8,
        'day_id': 9,
      });
      expect(log.customerId, 7);
      expect(log.planId, 8);
      expect(log.dayId, 9);

      final fromNested = LoggedSet.fromJson({'exercise': 5, 'set_number': 2});
      expect(fromNested.exerciseId, 5);
    });

    test('LoggedSet defaults set_number to 1 and is_completed to true', () {
      expect(LoggedSet.fromJson({}).setNumber, 1);
      expect(LoggedSet.fromJson({}).isCompleted, isTrue);
    });
  });

  group('WorkoutDay / WorkoutPlan', () {
    test('parses a plan with days and round-trips', () {
      final plan = WorkoutPlan.fromJson({
        'id': 1,
        'name': 'Beginner Strength',
        'description': '3x/week full body',
        'difficulty': 'beginner',
        'duration_weeks': 6,
        'sessions_per_week': 3,
        'days': [
          {
            'id': 1,
            'name': 'Day A',
            'day_number': 1,
            'exercises': [
              {
                'exercise': {'id': 5, 'name': 'Squat'},
                'target_sets': 3,
              },
            ],
          },
        ],
      });

      expect(plan.name, 'Beginner Strength');
      expect(plan.difficulty, 'beginner');
      expect(plan.sessionsPerWeek, 3);
      expect(plan.days, hasLength(1));
      expect(plan.days.first.exercises, hasLength(1));
      expect(plan.days.first.exercises.first.exercise.name, 'Squat');

      final reparsed = WorkoutPlan.fromJson(plan.toJson());
      expect(reparsed.durationWeeks, 6);
      expect(reparsed.days.first.exercises, hasLength(1));
    });

    test('defaults names and tolerates missing lists', () {
      expect(WorkoutPlan.fromJson({'id': 1}).name, 'Workout Plan');
      expect(WorkoutDay.fromJson({}).name, 'Workout Day');
      expect(WorkoutDay.fromJson({}).exercises, isEmpty);
    });
  });

  group('WorkoutAssignment', () {
    test('parses canonical and alias keys', () {
      final a = WorkoutAssignment.fromJson({
        'id': 1,
        'customer': 10,
        'plan': 20,
        'plan_name': 'Beginner Strength',
        'assigned_at': '2026-06-01T00:00:00Z',
      });
      final b = WorkoutAssignment.fromJson({
        'id': 2,
        'customer_id': 11,
        'plan_id': 21,
        'start_date': '2026-06-02T00:00:00Z',
        'end_date': '2026-07-02T00:00:00Z',
      });

      expect(a.customerId, 10);
      expect(a.planId, 20);
      expect(a.planName, 'Beginner Strength');
      expect(a.assignedAt, DateTime.parse('2026-06-01T00:00:00Z'));
      expect(b.customerId, 11);
      expect(b.startDate, DateTime.parse('2026-06-02T00:00:00Z'));
      expect(b.endDate, DateTime.parse('2026-07-02T00:00:00Z'));
    });

    test('degrades missing refs to 0 and defaults is_active', () {
      final a = WorkoutAssignment.fromJson({'id': 1});
      expect(a.customerId, 0);
      expect(a.planId, 0);
      expect(a.isActive, isTrue);
    });
  });
}