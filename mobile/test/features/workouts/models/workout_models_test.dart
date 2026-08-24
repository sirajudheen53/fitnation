import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/workouts/data/models/exercise.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_exercise.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_plan.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_log.dart';

void main() {
  group('Exercise', () {
    test('fromJson parses all fields', () {
      final json = {
        'id': 1,
        'name': 'Bench Press',
        'description': 'Chest exercise',
        'category': 'strength',
        'difficulty': 'intermediate',
        'muscle_group': 'chest',
        'equipment': 'barbell',
        'instructions': ['Lie down', 'Press up'],
      };

      final exercise = Exercise.fromJson(json);

      expect(exercise.id, 1);
      expect(exercise.name, 'Bench Press');
      expect(exercise.category, 'strength');
      expect(exercise.muscleGroup, 'chest');
      expect(exercise.instructions.length, 2);
    });

    test('fromJson handles missing optional fields', () {
      final exercise = Exercise.fromJson({'id': 1, 'name': 'Squat'});
      expect(exercise.id, 1);
      expect(exercise.name, 'Squat');
      expect(exercise.category, isNull);
      expect(exercise.instructions, isEmpty);
    });
  });

  group('WorkoutExercise', () {
    test('fromJson parses exercise and sets', () {
      final json = {
        'id': 10,
        'exercise': {'id': 1, 'name': 'Bench Press'},
        'target_sets': 3,
        'target_reps': 10,
        'rest_seconds': 60,
        'sets': [
          {'set_number': 1, 'weight': 50.0, 'reps': 10},
          {'set_number': 2, 'weight': 55.0, 'reps': 8},
        ],
      };

      final we = WorkoutExercise.fromJson(json);

      expect(we.id, 10);
      expect(we.exercise.name, 'Bench Press');
      expect(we.targetSets, 3);
      expect(we.targetReps, 10);
      expect(we.sets.length, 2);
      expect(we.sets.first.weight, 50.0);
    });
  });

  group('WorkoutPlan', () {
    test('fromJson parses plan with days', () {
      final json = {
        'id': 1,
        'name': 'Beginner Plan',
        'difficulty': 'beginner',
        'duration_weeks': 4,
        'days': [
          {
            'id': 1,
            'name': 'Day 1',
            'day_number': 1,
            'exercises': [
              {
                'id': 1,
                'exercise': {'id': 1, 'name': 'Squat'},
              },
            ],
          },
        ],
      };

      final plan = WorkoutPlan.fromJson(json);

      expect(plan.id, 1);
      expect(plan.name, 'Beginner Plan');
      expect(plan.days.length, 1);
      expect(plan.days.first.exercises.length, 1);
    });
  });

  group('WorkoutAssignment', () {
    test('fromJson parses assignment', () {
      final json = {
        'id': 5,
        'customer': 3,
        'plan': 1,
        'plan_name': 'Beginner Plan',
        'is_active': true,
      };

      final assignment = WorkoutAssignment.fromJson(json);

      expect(assignment.id, 5);
      expect(assignment.customerId, 3);
      expect(assignment.planId, 1);
      expect(assignment.planName, 'Beginner Plan');
      expect(assignment.isActive, true);
    });
  });

  group('WorkoutLog', () {
    test('toJson produces correct payload', () {
      final log = WorkoutLog(
        customerId: 3,
        planId: 1,
        dayId: 1,
        durationMinutes: 45,
        sets: [
          LoggedSet(exerciseId: 1, setNumber: 1, weight: 50.0, reps: 10),
        ],
      );

      final json = log.toJson();

      expect(json['customer'], 3);
      expect(json['plan'], 1);
      expect(json['day'], 1);
      expect(json['duration_minutes'], 45);
      expect((json['sets'] as List).length, 1);
    });
  });
}
