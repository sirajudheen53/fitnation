import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/plans/presentation/providers/plan_assignment_providers.dart';
import 'package:fitnation_app/features/plans/presentation/screens/diet_plans_screen.dart';

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
        child: const MaterialApp(home: Scaffold(body: DietPlansScreen())),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('renders the assigned meal plan', (tester) async {
    remote.dietResult = [dietAssignment()];

    await pumpScreen(tester);

    expect(find.text('High Protein Cut'), findsOneWidget);
    expect(find.text('Active'), findsOneWidget);
    expect(find.text('Started 02 Oct 2026'), findsOneWidget);
  });

  testWidgets('shows the empty state when nothing is assigned', (tester) async {
    await pumpScreen(tester);

    expect(find.text('No meal plan yet'), findsOneWidget);
    expect(
      find.textContaining('hasn\'t assigned you a meal plan'),
      findsOneWidget,
    );
  });

  testWidgets('shows the error state with a working retry', (tester) async {
    remote.dietError = const AuthFailure(message: 'Not authorized');

    await pumpScreen(tester);

    expect(find.text('Not authorized'), findsOneWidget);

    remote.dietError = null;
    remote.dietResult = [dietAssignment()];
    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();

    expect(find.text('High Protein Cut'), findsOneWidget);
    expect(remote.dietCalls, 2);
  });

  testWidgets('loads assignments when the tab mounts', (tester) async {
    await pumpScreen(tester);

    expect(remote.dietCalls, 1);
  });
}
