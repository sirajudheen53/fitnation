import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/workouts/data/models/exercise.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_exercise.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_plan.dart';
import 'package:fitnation_app/features/workouts/presentation/providers/workout_provider.dart';
import 'package:fitnation_app/features/workouts/presentation/screens/workout_list_screen.dart';

void main() {
  final assignment = WorkoutAssignment(
    id: 1,
    customerId: 3,
    planId: 10,
    planName: 'Beginner Plan',
    isActive: true,
  );

  final plan = WorkoutPlan(
    id: 10,
    name: 'Beginner Plan',
    difficulty: 'beginner',
    durationWeeks: 4,
    days: [
      WorkoutDay(
        id: 1,
        name: 'Day 1',
        dayNumber: 1,
        exercises: [
          WorkoutExercise(
            id: 1,
            exercise: const Exercise(id: 1, name: 'Squat', muscleGroup: 'legs'),
            targetSets: 3,
            targetReps: 10,
          ),
        ],
      ),
    ],
  );

  Widget buildWidget() {
    return ProviderScope(
      overrides: [
        activeWorkoutAssignmentProvider
            .overrideWith((ref) async => assignment),
        workoutPlanProvider.overrideWith((ref, planId) async => plan),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const WorkoutListScreen(),
      ),
    );
  }

  testWidgets('renders plan name and workout days', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.text('Beginner Plan'), findsOneWidget);
    expect(find.text('Workout Days'), findsOneWidget);
    expect(find.text('Day 1'), findsOneWidget);
    expect(find.text('1 exercises'), findsOneWidget);
  });

  testWidgets('renders empty state when no assignment', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          activeWorkoutAssignmentProvider.overrideWith((ref) async => null),
        ],
        child: MaterialApp(
          theme: AppTheme.light,
          home: const WorkoutListScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('No active workout plan'), findsOneWidget);
  });
}
