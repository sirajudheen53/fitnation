import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/diet/data/data_sources/diet_remote_data_source.dart';
import '../../../helpers/canned_adapter.dart';

void main() {
  group('DietRemoteDataSource', () {
    test('getActiveAssignment queries the active plan for the customer', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'results': [
                  {'id': 1, 'customer_id': 10, 'plan_id': 20, 'plan_name': 'Cut 8 weeks'},
                ],
              }),
        ],
      );
      final source = DietRemoteDataSource(dio);

      final assignment = await source.getActiveAssignment(10);

      expect(assignment!.planName, 'Cut 8 weeks');
      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.uri.path, '/diet-assignments/');
      expect(call.recorded.single.uri.queryParameters['customer'], '10');
      expect(call.recorded.single.uri.queryParameters['is_active'], 'true');
    });

    test('an empty page means no active assignment', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(200, {'results': []})],
      );
      final source = DietRemoteDataSource(dio);

      expect(await source.getActiveAssignment(10), isNull);
    });

    test('getDietPlan fetches the plan by id', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'id': 20,
                'name': 'Cut 8 weeks',
                'target_calories': 1800,
                'days': [
                  {
                    'name': 'Day 1',
                    'meals': [
                      {
                        'name': 'Lunch',
                        'food_items': [
                          {'name': 'Rice', 'calories': 400, 'protein': 10},
                        ],
                      },
                    ],
                  },
                ],
              }),
        ],
      );
      final source = DietRemoteDataSource(dio);

      final plan = await source.getDietPlan(20);

      expect(plan.id, 20);
      expect(plan.targetCalories, 1800);
      expect(plan.days.single.meals.single.totalCalories, 400);
      expect(
        (dio.httpClientAdapter as CannedAdapter).recorded.single.uri.path,
        '/diet-plans/20/',
      );
    });

    test('setMealCompleted PATCHes the meal with the flag', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(200, {'id': 4, 'is_completed': true})],
      );
      final source = DietRemoteDataSource(dio);

      await source.setMealCompleted(4, true);

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.method, 'PATCH');
      expect(call.recorded.single.uri.path, '/diet-meals/4/');
      expect(call.recorded.single.bodyMap, {'is_completed': true});
    });

    test('errors map to the failure ladder', () async {
      final forbidden = Dio()..httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(403, {'detail': 'No active membership'})],
      );
      await expectLater(
        DietRemoteDataSource(forbidden).getActiveAssignment(10),
        throwsA(
          isA<AuthFailure>().having((f) => f.message, 'message', 'No active membership'),
        ),
      );

      final network = Dio()..httpClientAdapter = CannedAdapter(
        throws: () => DioException(
          requestOptions: RequestOptions(path: '/x'),
          type: DioExceptionType.connectionError,
        ),
      );
      await expectLater(
        DietRemoteDataSource(network).getDietPlan(20),
        throwsA(isA<NetworkFailure>()),
      );
    });
  });
}