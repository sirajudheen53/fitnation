import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/progress/data/data_sources/progress_remote_data_source.dart';
import '../../../helpers/canned_adapter.dart';

void main() {
  group('ProgressRemoteDataSource.getMeasurements', () {
    test('GETs the measurements endpoint and parses a paginated payload', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'results': [
                  {
                    'id': 1,
                    'weight_kg': 72.4,
                    'height_cm': 175,
                    'bmi': 23.6,
                    'body_fat_percentage': 18.2,
                    'chest_cm': 98,
                    'waist_cm': 81,
                    'hips_cm': 96,
                    'arms_cm': 33,
                    'thighs_cm': 55,
                  },
                  {'id': 2},
                ],
              }),
        ],
      );
      final source = ProgressRemoteDataSource(dio);

      final measurements = await source.getMeasurements(5);

      expect(measurements, hasLength(2));
      expect(measurements.first.weight, 72.4);
      expect(measurements.first.bodyFat, 18.2);
      expect(measurements.last.weight, isNull);
      expect(measurements.first.measuredAt, isNull);

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.method, 'GET');
      expect(call.recorded.single.uri.path, '/customers/customers/5/measurements/');
    });

    test('accepts a bare list body and degrades junk to an empty list', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, [
                {'id': 9, 'weight': 80},
              ]),
          () => cannedResponse(200, {'nope': true}),
        ],
      );
      final source = ProgressRemoteDataSource(dio);

      expect((await source.getMeasurements(1)).single.weight, 80.0);
      expect(await source.getMeasurements(1), isEmpty);
    });
  });

  group('ProgressRemoteDataSource.getFitnessGoals', () {
    test('GETs the fitness-goals endpoint', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'results': [
                  {
                    'id': 3,
                    'goal_type': 'weight_loss',
                    'target_weight': 68,
                    'target_date': '2026-12-31T00:00:00Z',
                    'is_active': true,
                  },
                ],
              }),
        ],
      );
      final source = ProgressRemoteDataSource(dio);

      final goals = await source.getFitnessGoals(5);

      expect(goals, hasLength(1));
      expect(goals.single.goalType, 'weight_loss');
      expect(goals.single.targetWeight, 68.0);
      expect(goals.single.isActive, isTrue);
      expect(
        (dio.httpClientAdapter as CannedAdapter).recorded.single.uri.path,
        '/customers/customers/5/fitness-goals/',
      );
    });
  });

  group('error mapping', () {
    test('a connection error becomes a NetworkFailure', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        throws: () => DioException(
          requestOptions: RequestOptions(path: '/x'),
          type: DioExceptionType.connectionError,
        ),
      );
      final source = ProgressRemoteDataSource(dio);

      await expectLater(
        source.getMeasurements(1),
        throwsA(isA<NetworkFailure>()),
      );
    });

    test('a 401 becomes an AuthFailure carrying the detail', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(401, {'detail': 'Session expired'})],
      );
      final source = ProgressRemoteDataSource(dio);

      await expectLater(
        source.getMeasurements(1),
        throwsA(
          isA<AuthFailure>()
              .having((f) => f.statusCode, 'statusCode', 401)
              .having((f) => f.message, 'message', 'Session expired'),
        ),
      );
    });

    test('a 400 becomes a ValidationFailure carrying the field errors', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(400, {'weight_kg': ['Invalid']})],
      );
      final source = ProgressRemoteDataSource(dio);

      await expectLater(
        source.getMeasurements(1),
        throwsA(
          isA<ValidationFailure>()
              .having((f) => f.statusCode, 'statusCode', 400)
              .having((f) => f.errors, 'errors', {'weight_kg': ['Invalid']}),
        ),
      );
    });

    test('other statuses become a ServerFailure with a default message', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(500, {'bogus': 1})],
      );
      final source = ProgressRemoteDataSource(dio);

      await expectLater(
        source.getFitnessGoals(1),
        throwsA(
          isA<ServerFailure>()
              .having((f) => f.statusCode, 'statusCode', 500)
              .having((f) => f.message, 'message', 'Server error'),
        ),
      );
    });

    test('a cancelled request becomes an UnknownFailure', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        throws: () => DioException(
          requestOptions: RequestOptions(path: '/x'),
          type: DioExceptionType.cancel,
          message: 'cancelled',
        ),
      );
      final source = ProgressRemoteDataSource(dio);

      await expectLater(
        source.getFitnessGoals(1),
        throwsA(isA<UnknownFailure>()),
      );
    });
  });
}