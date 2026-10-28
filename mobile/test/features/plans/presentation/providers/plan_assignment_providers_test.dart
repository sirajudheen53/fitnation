import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/plans/presentation/providers/plan_assignment_providers.dart';

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

  group('workoutAssignmentsProvider', () {
    test('starts idle before any load', () {
      expect(
        container.read(workoutAssignmentsProvider).status,
        PlanAssignmentsStatus.idle,
      );
    });

    test('load transitions idle → loaded with assignments', () async {
      remote.workoutResult = [workoutAssignment(), workoutAssignment(id: 2)];

      await container.read(workoutAssignmentsProvider.notifier).load();

      final state = container.read(workoutAssignmentsProvider);
      expect(state.status, PlanAssignmentsStatus.loaded);
      expect(state.assignments, hasLength(2));
      expect(state.errorMessage, isNull);
    });

    test('load surfaces the failure message on error', () async {
      remote.workoutError = const AuthFailure(message: 'Not authorized');

      await container.read(workoutAssignmentsProvider.notifier).load();

      final state = container.read(workoutAssignmentsProvider);
      expect(state.status, PlanAssignmentsStatus.error);
      expect(state.errorMessage, 'Not authorized');
      expect(state.assignments, isEmpty);
    });

    test('empty backend list still lands in loaded', () async {
      await container.read(workoutAssignmentsProvider.notifier).load();

      final state = container.read(workoutAssignmentsProvider);
      expect(state.status, PlanAssignmentsStatus.loaded);
      expect(state.assignments, isEmpty);
    });

    test('a failed refresh keeps previously loaded assignments', () async {
      remote.workoutResult = [workoutAssignment()];
      await container.read(workoutAssignmentsProvider.notifier).load();

      remote.workoutError = const ServerFailure(message: 'Boom.');
      await container.read(workoutAssignmentsProvider.notifier).load();

      final state = container.read(workoutAssignmentsProvider);
      expect(state.status, PlanAssignmentsStatus.error);
      expect(state.assignments, hasLength(1));
    });
  });

  group('dietAssignmentsProvider', () {
    test('load transitions idle → loaded with assignments', () async {
      remote.dietResult = [dietAssignment()];

      await container.read(dietAssignmentsProvider.notifier).load();

      final state = container.read(dietAssignmentsProvider);
      expect(state.status, PlanAssignmentsStatus.loaded);
      expect(state.assignments, hasLength(1));
      expect(state.assignments.first.dietPlanName, 'High Protein Cut');
    });

    test('load surfaces the failure message on error', () async {
      remote.dietError = const ServerFailure(message: 'Server error');

      await container.read(dietAssignmentsProvider.notifier).load();

      final state = container.read(dietAssignmentsProvider);
      expect(state.status, PlanAssignmentsStatus.error);
      expect(state.errorMessage, 'Server error');
    });
  });
}
