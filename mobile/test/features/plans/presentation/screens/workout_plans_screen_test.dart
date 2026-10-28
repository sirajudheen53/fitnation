import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/plans/data/models/workout_assignment_model.dart';
import 'package:fitnation_app/features/plans/presentation/providers/plan_assignment_providers.dart';
import 'package:fitnation_app/features/plans/presentation/screens/workout_plans_screen.dart';

import '../../../../helpers/plan_assignment_fakes.dart';

void main() {
  late FakePlanAssignmentRemoteDataSource remote;
  late ProviderContainer container;

  setUp(() {
    remote = FakePlanAssignmentRemoteDataSource();
    container = ProviderContainer(
      overrides: [
        planAssignmentRepositoryProvider
            .overrideWithValue(FakePlanAssignmentRepository(remote)),
      ],
    );
  });

  tearDown(() => container.dispose());

  Future<void> pumpScreen(WidgetTester tester) async {
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: WorkoutPlansScreen())),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('renders the assigned workout plan', (tester) async {
    remote.workoutResult = [workoutAssignment(), workoutAssignment(id: 2)];

    await pumpScreen(tester);

    expect(find.text('Beginner Strength'), findsNWidgets(2));
    expect(find.text('Active'), findsNWidgets(2));
    expect(find.text('Started 01 Oct 2026'), findsNWidgets(2));
    // The canned rows carry no notes — the notes box must not render.
    expect(find.byKey(const ValueKey(1)), findsOneWidget);
  });

  testWidgets('renders start→end range and trainer notes when present', (
    tester,
  ) async {
    remote.workoutResult = [
      WorkoutAssignmentModel(
        id: 7,
        customer: 2,
        workoutPlan: 3,
        workoutPlanName: 'Cut Phase',
        customerName: 'Arjun Nair',
        startDate: DateTime(2026, 10, 1),
        endDate: DateTime(2026, 12, 15),
        notes: 'Deload every 4th week.',
        createdAt: DateTime(2026, 10, 1),
        updatedAt: DateTime(2026, 10, 1),
      ),
    ];

    await pumpScreen(tester);

    expect(find.text('01 Oct 2026 → 15 Dec 2026'), findsOneWidget);
    expect(find.text('Deload every 4th week.'), findsOneWidget);
  });

  testWidgets('shows the empty state when nothing is assigned', (tester) async {
    await pumpScreen(tester);

    expect(find.text('No workout plan yet'), findsOneWidget);
    expect(
      find.textContaining('hasn\'t assigned you a workout plan'),
      findsOneWidget,
    );
  });

  testWidgets('shows the error state with a working retry', (tester) async {
    remote.workoutError = const ServerFailure(message: 'Server error');

    await pumpScreen(tester);

    expect(find.text('Server error'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);

    remote.workoutError = null;
    remote.workoutResult = [workoutAssignment()];
    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();

    expect(find.text('Beginner Strength'), findsOneWidget);
    expect(remote.workoutCalls, 2); // initial load + retry
  });

  testWidgets('loads assignments when the tab mounts', (tester) async {
    await pumpScreen(tester);

    expect(remote.workoutCalls, 1);
  });
}
