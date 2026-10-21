import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/workouts/data/data_sources/workout_remote_data_source.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_log.dart';
import '../../../helpers/canned_adapter.dart';

void main() {
  group('WorkoutRemoteDataSource.getActiveAssignment', () {
    test('queries by customer and is_active, and returns the first hit', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'results': [
                  {
                    'id': 1,
                    'customer_id': 10,
                    'plan_id': 20,
                    'plan_name': 'Beginner Strength',
                  },
                ],
              }),
        ],
      );
      final source = WorkoutRemoteDataSource(dio);

      final assignment = await source.getActiveAssignment(10);

      expect(assignment, isNotNull);
      expect(assignment!.customerId, 10);
      expect(assignment.planName, 'Beginner Strength');

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.uri.path, '/workouts/workout-assignments/');
      expect(call.recorded.single.uri.queryParameters['customer'], '10');
      expect(call.recorded.single.uri.queryParameters['is_active'], 'true');
    });

    test('an empty page means no active assignment', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(200, {'results': []})],
      );
      final source = WorkoutRemoteDataSource(dio);

      expect(await source.getActiveAssignment(10), isNull);
    });
  });

  group('WorkoutRemoteDataSource.getWorkoutPlan', () {
    test('GETs the plan by id and parses it', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'id': 20,
                'name': 'Beginner Strength',
                'duration_weeks': 6,
                'days': [
                  {'name': 'Day A'},
                ],
              }),
        ],
      );
      final source = WorkoutRemoteDataSource(dio);

      final plan = await source.getWorkoutPlan(20);

      expect(plan.id, 20);
      expect(plan.days, hasLength(1));
      expect(
        (dio.httpClientAdapter as CannedAdapter).recorded.single.uri.path,
        '/workouts/workout-plans/20/',
      );
    });
  });

  group('WorkoutRemoteDataSource.getExercises', () {
    test('passes optional filters as query parameters', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'results': [
                  {'id': 5, 'name': 'Squat', 'muscle_group': 'legs'},
                ],
              }),
          () => cannedResponse(200, {'results': []}),
        ],
      );
      final source = WorkoutRemoteDataSource(dio);

      final exercises = await source.getExercises(
        category: 'strength',
        difficulty: 'beginner',
        muscleGroup: 'legs',
      );
      expect(exercises.single.name, 'Squat');

      final call = dio.httpClientAdapter as CannedAdapter;
      final q1 = call.recorded.first.uri.queryParameters;
      expect(q1['category'], 'strength');
      expect(q1['difficulty'], 'beginner');
      expect(q1['muscle_group'], 'legs');

      await source.getExercises();
      expect(call.recorded.last.uri.queryParameters, isEmpty);
    });

    test('getExercise fetches one by id', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {'id': 5, 'name': 'Squat'}),
        ],
      );
      final source = WorkoutRemoteDataSource(dio);

      final exercise = await source.getExercise(5);

      expect(exercise.id, 5);
      expect(
        (dio.httpClientAdapter as CannedAdapter).recorded.single.uri.path,
        '/exercises/exercises/5/',
      );
    });
  });

  group('WorkoutRemoteDataSource.logWorkout', () {
    test('POSTs the log payload and parses the response', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(201, {
                'id': 42,
                'duration_minutes': 45,
                'calories_burned': 320,
                'sets': [],
              }),
        ],
      );
      final source = WorkoutRemoteDataSource(dio);

      final parsed = await source.logWorkout(
        const WorkoutLog(customerId: 10, durationMinutes: 45),
      );

      expect(parsed.id, 42);
      expect(parsed.caloriesBurned, 320);

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.method, 'POST');
      expect(call.recorded.single.uri.path, '/workouts/workout-logs/');
      expect(call.recorded.single.bodyMap, {'customer': 10, 'duration_minutes': 45, 'sets': []});
    });

    test('errors map to the matching failures', () async {
      final network = Dio()..httpClientAdapter = CannedAdapter(
        throws: () => DioException(
          requestOptions: RequestOptions(path: '/x'),
          type: DioExceptionType.sendTimeout,
        ),
      );
      await expectLater(
        WorkoutRemoteDataSource(network).getActiveAssignment(1),
        throwsA(isA<NetworkFailure>()),
      );

      final server = Dio()..httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(404, {'detail': 'No such plan'})],
      );
      await expectLater(
        WorkoutRemoteDataSource(server).getWorkoutPlan(99),
        throwsA(
          isA<ServerFailure>()
              .having((f) => f.statusCode, 'statusCode', 404)
              .having((f) => f.message, 'message', 'No such plan'),
        ),
      );
    });
  });
}