import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/auth/data/data_sources/api_client.dart';
import 'package:fitnation_app/features/plans/data/data_sources/plan_assignment_remote_data_source.dart';

import '../../../../helpers/fakes.dart';

void main() {
  Map<String, dynamic> workoutRow({int id = 11}) => {
        'id': id,
        'customer': 42,
        'workout_plan': 7,
        'workout_plan_name': 'Beginner Strength',
        'customer_name': 'Arjun Nair',
        'customer_is_deleted': false,
        'start_date': '2026-10-01',
        'end_date': null,
        'is_active': true,
        'assigned_by': 3,
        'notes': 'Focus on form.',
        'created_at': '2026-10-01T09:15:00Z',
        'updated_at': '2026-10-05T18:40:00Z',
      };

  Map<String, dynamic> dietRow({int id = 21}) => {
        'id': id,
        'customer': 42,
        'diet_plan': 9,
        'diet_plan_name': 'High Protein Cut',
        'customer_name': 'Arjun Nair',
        'customer_is_deleted': false,
        'start_date': '2026-10-02',
        'end_date': null,
        'is_active': true,
        'assigned_by': 3,
        'notes': null,
        'created_at': '2026-10-02T08:00:00Z',
        'updated_at': '2026-10-02T08:00:00Z',
      };

  test('fetchActiveWorkoutAssignments GETs the active endpoint and parses', () async {
    final requests = <RequestOptions>[];
    final adapter = FakeDioAdapter((options) {
      requests.add(options);
      return FakeDioAdapter.jsonList([workoutRow(), workoutRow(id: 12)]);
    });
    final source = PlanAssignmentRemoteDataSource(FakeDioAdapter.client(adapter));

    final assignments = await source.fetchActiveWorkoutAssignments();

    expect(assignments, hasLength(2));
    expect(assignments.first.workoutPlanName, 'Beginner Strength');
    expect(requests.single.method, 'GET');
    expect(requests.single.path, '/workouts/workout-assignments/active/');
  });

  test('fetchActiveDietAssignments GETs the active endpoint and parses', () async {
    final requests = <RequestOptions>[];
    final adapter = FakeDioAdapter((options) {
      requests.add(options);
      return FakeDioAdapter.jsonList([dietRow()]);
    });
    final source = PlanAssignmentRemoteDataSource(FakeDioAdapter.client(adapter));

    final assignments = await source.fetchActiveDietAssignments();

    expect(assignments, hasLength(1));
    expect(assignments.first.dietPlanName, 'High Protein Cut');
    expect(requests.single.method, 'GET');
    expect(requests.single.path, '/diet-assignments/active/');
  });

  test('401 maps to AuthFailure carrying the backend detail', () async {
    final adapter = FakeDioAdapter((options) =>
        FakeDioAdapter.json({'detail': 'Invalid token.'}, 401));
    final source = PlanAssignmentRemoteDataSource(FakeDioAdapter.client(adapter));

    await expectLater(
      source.fetchActiveWorkoutAssignments(),
      throwsA(
        isA<AuthFailure>()
            .having((f) => f.statusCode, 'statusCode', 401)
            .having((f) => f.message, 'message', 'Invalid token.'),
      ),
    );
  });

  test('403 (e.g. missing tenant entitlement) maps to AuthFailure', () async {
    final adapter = FakeDioAdapter(
        (options) => FakeDioAdapter.json({'detail': 'Denied.'}, 403));
    final source = PlanAssignmentRemoteDataSource(FakeDioAdapter.client(adapter));

    await expectLater(
      source.fetchActiveDietAssignments(),
      throwsA(isA<AuthFailure>().having((f) => f.statusCode, 'statusCode', 403)),
    );
  });

  test('500 maps to ServerFailure', () async {
    final adapter = FakeDioAdapter(
        (options) => FakeDioAdapter.json({'detail': 'Boom.'}, 500));
    final source = PlanAssignmentRemoteDataSource(FakeDioAdapter.client(adapter));

    await expectLater(
      source.fetchActiveWorkoutAssignments(),
      throwsA(
        isA<ServerFailure>()
            .having((f) => f.statusCode, 'statusCode', 500)
            .having((f) => f.message, 'message', 'Boom.'),
      ),
    );
  });

  test('connection errors map to NetworkFailure', () async {
    final adapter = FakeDioAdapter((options) => throw DioException.connectionError(
          requestOptions: options,
          reason: 'offline',
        ));
    final source = PlanAssignmentRemoteDataSource(FakeDioAdapter.client(adapter));

    await expectLater(
      source.fetchActiveDietAssignments(),
      throwsA(isA<NetworkFailure>()),
    );
  });

  test('sends the session token as the Authorization header', () async {
    ApiClient.reset();
    final requests = <RequestOptions>[];
    final dio = ApiClient.getInstance(token: 'session-token-1');
    final adapter = FakeDioAdapter((options) {
      requests.add(options);
      return FakeDioAdapter.jsonList(const <dynamic>[]);
    });
    dio.httpClientAdapter = adapter;
    final source = PlanAssignmentRemoteDataSource(dio);

    final assignments = await source.fetchActiveWorkoutAssignments();

    expect(assignments, isEmpty);
    expect(
      requests.single.headers['Authorization'],
      'Token session-token-1',
    );
    ApiClient.reset();
  });
}
