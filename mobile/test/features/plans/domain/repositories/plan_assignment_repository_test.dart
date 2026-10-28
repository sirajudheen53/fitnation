import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/plans/domain/repositories/plan_assignment_repository.dart';

import '../../../../helpers/fakes.dart';
import '../../../../helpers/plan_assignment_fakes.dart';

void main() {
  late FakePlanAssignmentRemoteDataSource remote;
  late PlanAssignmentRepository repository;

  setUp(() {
    remote = FakePlanAssignmentRemoteDataSource();
    repository = PlanAssignmentRepository(remote);
  });

  group('activeWorkoutAssignments', () {
    test('returns assignments on success', () async {
      remote.workoutResult = [workoutAssignment(), workoutAssignment(id: 2)];

      final result = await repository.activeWorkoutAssignments();

      expect(result.error, isNull);
      expect(result.assignments, hasLength(2));
      expect(remote.workoutCalls, 1);
    });

    test('returns the thrown Failure', () async {
      remote.workoutError = const NetworkFailure();

      final result = await repository.activeWorkoutAssignments();

      expect(result.assignments, isNull);
      expectFailure(result.error, NetworkFailure);
    });

    test('wraps unexpected throws as UnknownFailure', () async {
      remote.workoutError = StateError('boom');

      final result = await repository.activeWorkoutAssignments();

      expectFailure(result.error, UnknownFailure, messageContains: 'boom');
    });
  });

  group('activeDietAssignments', () {
    test('returns assignments on success', () async {
      remote.dietResult = [dietAssignment()];

      final result = await repository.activeDietAssignments();

      expect(result.error, isNull);
      expect(result.assignments, hasLength(1));
      expect(remote.dietCalls, 1);
    });

    test('returns the thrown Failure', () async {
      remote.dietError = const AuthFailure(message: 'denied');

      final result = await repository.activeDietAssignments();

      expect(result.assignments, isNull);
      expectFailure(result.error, AuthFailure);
    });

    test('wraps unexpected throws as UnknownFailure', () async {
      remote.dietError = StateError('nope');

      final result = await repository.activeDietAssignments();

      expectFailure(result.error, UnknownFailure, messageContains: 'nope');
    });
  });
}
