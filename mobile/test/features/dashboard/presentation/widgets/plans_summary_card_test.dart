import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/dashboard/presentation/widgets/plans_summary_card.dart';
import 'package:fitnation_app/features/plans/data/models/diet_assignment_model.dart';
import 'package:fitnation_app/features/plans/data/models/workout_assignment_model.dart';
import 'package:fitnation_app/features/plans/presentation/providers/plan_assignment_providers.dart';

import '../../../../helpers/plan_assignment_fakes.dart';

void main() {
  Future<void> pumpCard(
    WidgetTester tester, {
    required PlanAssignmentsState<WorkoutAssignmentModel> workouts,
    required PlanAssignmentsState<DietAssignmentModel> diet,
    VoidCallback? onOpenWorkouts,
    VoidCallback? onOpenDiet,
  }) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: PlansSummaryCard(
              workouts: workouts,
              diet: diet,
              onOpenWorkouts: onOpenWorkouts,
              onOpenDiet: onOpenDiet,
            ),
          ),
        ),
      ),
    );
  }

  testWidgets('hidden entirely when the member has neither plan tab', (
    tester,
  ) async {
    await pumpCard(
      tester,
      workouts: const PlanAssignmentsState(),
      diet: const PlanAssignmentsState(),
    );

    expect(find.text('Your plans'), findsNothing);
  });

  testWidgets('lists the assigned workout plan and count', (tester) async {
    await pumpCard(
      tester,
      workouts: PlanAssignmentsState(
        status: PlanAssignmentsStatus.loaded,
        assignments: [workoutAssignment()],
      ),
      diet: const PlanAssignmentsState(
        status: PlanAssignmentsStatus.loaded,
      ),
      onOpenWorkouts: () {},
      onOpenDiet: () {},
    );

    expect(find.text('Your plans'), findsOneWidget);
    expect(find.text('Workout plans'), findsOneWidget);
    expect(find.text('Beginner Strength'), findsOneWidget);
    expect(find.text('Meal plans'), findsOneWidget);
    expect(find.text('None assigned'), findsOneWidget);
  });

  testWidgets('several assignments collapse into a count', (tester) async {
    await pumpCard(
      tester,
      workouts: PlanAssignmentsState(
        status: PlanAssignmentsStatus.loaded,
        assignments: [workoutAssignment(), workoutAssignment(id: 2)],
      ),
      diet: const PlanAssignmentsState(status: PlanAssignmentsStatus.loaded),
      onOpenWorkouts: () {},
      onOpenDiet: () {},
    );

    expect(find.text('Beginner Strength +1 more'), findsOneWidget);
  });

  testWidgets('loading and error details are per-row', (tester) async {
    await pumpCard(
      tester,
      workouts: const PlanAssignmentsState(
        status: PlanAssignmentsStatus.loading,
      ),
      diet: const PlanAssignmentsState(
        status: PlanAssignmentsStatus.error,
        errorMessage: 'Network error. Check your connection.',
      ),
      onOpenWorkouts: () {},
      onOpenDiet: () {},
    );

    expect(find.text('Loading…'), findsOneWidget);
    expect(find.text('Couldn\'t load'), findsOneWidget);
  });

  testWidgets('tapping a row opens the matching tab', (tester) async {
    var openedWorkouts = false;
    var openedDiet = false;
    await pumpCard(
      tester,
      workouts: PlanAssignmentsState(
        status: PlanAssignmentsStatus.loaded,
        assignments: [workoutAssignment()],
      ),
      diet: const PlanAssignmentsState(status: PlanAssignmentsStatus.loaded),
      onOpenWorkouts: () => openedWorkouts = true,
      onOpenDiet: () => openedDiet = true,
    );

    await tester.tap(find.text('Workout plans'));
    await tester.tap(find.text('Meal plans'));

    expect(openedWorkouts, isTrue);
    expect(openedDiet, isTrue);
  });
}
