import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/workouts/data/models/exercise.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_log.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_plan.dart';
import 'package:fitnation_app/features/workouts/domain/repositories/workout_repository.dart';
import 'package:fitnation_app/features/workouts/presentation/providers/workout_provider.dart';

class _CannedRepository implements WorkoutRepository {
  _CannedRepository({this.logResult});

  final (WorkoutLog?, Failure?)? logResult;

  @override
  Future<({WorkoutAssignment? assignment, Failure? error})>
      getActiveAssignment(int customerId) async {
    return (assignment: null, error: const ServerFailure(message: 'unused'));
  }

  @override
  Future<({WorkoutPlan? plan, Failure? error})> getWorkoutPlan(int planId) async {
    return (plan: null, error: const ServerFailure(message: 'unused'));
  }

  @override
  Future<({List<Exercise> exercises, Failure? error})> getExercises({
    String? category,
    String? difficulty,
    String? muscleGroup,
  }) async {
    return (
      exercises: const <Exercise>[],
      error: const ServerFailure(message: 'unused'),
    );
  }

  @override
  Future<({WorkoutLog? log, Failure? error})> logWorkout(WorkoutLog log) async {
    final canned = logResult!;
    return (log: canned.$1, error: canned.$2);
  }
}

void main() {
  ProviderContainer container(_CannedRepository repo) {
    final c = ProviderContainer(overrides: [
      workoutRepositoryProvider.overrideWithValue(repo),
    ]);
    addTearDown(c.dispose);
    return c;
  }

  const savedLog = WorkoutLog(customerId: 10, durationMinutes: 40);

  test('a saved log flips the state to success and keeps the log', () async {
    final c = container(_CannedRepository(logResult: (savedLog, null)));
    final notifier = c.read(workoutLogProvider.notifier);

    final ok = await notifier.logWorkout(savedLog);

    expect(ok, isTrue);
    final state = c.read(workoutLogProvider);
    expect(state.isSuccess, isTrue);
    expect(state.log!.durationMinutes, 40);
    expect(state.errorMessage, isNull);
  });

  test('a failure keeps the state empty and carries the message', () async {
    final c = container(_CannedRepository(
      logResult: (null, const ServerFailure(message: 'Gym backend down')),
    ));
    final notifier = c.read(workoutLogProvider.notifier);

    final ok = await notifier.logWorkout(savedLog);

    expect(ok, isFalse);
    final state = c.read(workoutLogProvider);
    expect(state.isSuccess, isFalse);
    expect(state.log, isNull);
    expect(state.errorMessage, 'Gym backend down');
  });

  test('reset clears the state', () async {
    final c = container(_CannedRepository(logResult: (savedLog, null)));
    final notifier = c.read(workoutLogProvider.notifier);
    await notifier.logWorkout(savedLog);

    notifier.reset();

    expect(c.read(workoutLogProvider), const WorkoutLogState());
  });
}