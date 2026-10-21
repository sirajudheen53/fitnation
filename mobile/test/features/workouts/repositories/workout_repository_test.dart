import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/workouts/data/data_sources/workout_remote_data_source.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_log.dart';
import 'package:fitnation_app/features/workouts/domain/repositories/workout_repository.dart';
import '../../../helpers/canned_adapter.dart';

void main() {
  WorkoutRepository repo(CannedAdapter adapter) {
    final dio = Dio()..httpClientAdapter = adapter;
    return WorkoutRepository(WorkoutRemoteDataSource(dio));
  }

  test('getActiveAssignment returns the assignment, or null with an error', () async {
    final ok = repo(CannedAdapter(
      calls: [
        () => cannedResponse(200, {
              'results': [
                {'id': 1, 'customer': 10, 'plan': 20},
              ],
            }),
      ],
    ));
    final (assignment: found, error: okError) = await ok.getActiveAssignment(10);
    expect(found!.customerId, 10);
    expect(okError, isNull);

    final down = repo(CannedAdapter(
      calls: [() => cannedResponse(500, {'detail': 'DB down'})],
    ));
    final (assignment: miss, error: failError) = await down.getActiveAssignment(10);
    expect(miss, isNull);
    expect(failError, isA<ServerFailure>());
  });

  test('getWorkoutPlan returns the plan, or the failure', () async {
    final ok = repo(CannedAdapter(
      calls: [
        () => cannedResponse(200, {'id': 20, 'name': 'Beginner Strength'}),
      ],
    ));
    final (plan: plan, error: planError) = await ok.getWorkoutPlan(20);
    expect(plan!.id, 20);
    expect(planError, isNull);

    final missing = repo(CannedAdapter(
      calls: [() => cannedResponse(404, {'detail': 'No such plan'})],
    ));
    final (plan: nothing, error: missingError) = await missing.getWorkoutPlan(99);
    expect(nothing, isNull);
    expect(missingError, isA<ServerFailure>().having((f) => f.statusCode, 'code', 404));
  });

  test('getExercises returns the list, or an empty list with the failure', () async {
    final ok = repo(CannedAdapter(
      calls: [
        () => cannedResponse(200, {
              'results': [
                {'id': 5, 'name': 'Squat'},
              ],
            }),
      ],
    ));
    final (exercises: list, error: okError) =
        await ok.getExercises(muscleGroup: 'legs');
    expect(list.single.name, 'Squat');
    expect(okError, isNull);

    final down = repo(CannedAdapter(
      calls: [() => cannedResponse(500, {'detail': 'x'})],
    ));
    final (exercises: empty, error: failError) = await down.getExercises();
    expect(empty, isEmpty);
    expect(failError, isA<ServerFailure>());
  });

  test('logWorkout posts through the data source', () async {
    final ok = repo(CannedAdapter(
      calls: [
        () => cannedResponse(201, {'id': 42, 'duration_minutes': 45, 'sets': []}),
      ],
    ));
    final (log: saved, error: logError) =
        await ok.logWorkout(const WorkoutLog(customerId: 10, durationMinutes: 45));
    expect(saved!.id, 42);
    expect(logError, isNull);

    final down = repo(CannedAdapter(
      calls: [() => cannedResponse(422, {'noop': 1})],
    ));
    final (log: rejected, error: logFailError) =
        await down.logWorkout(const WorkoutLog(customerId: 10));
    expect(rejected, isNull);
    expect(logFailError, isA<ServerFailure>());
  });
}