import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/ai_nutrition/data/data_sources/ai_nutrition_remote_data_source.dart';
import '../../../helpers/canned_adapter.dart';

void main() {
  group('AiNutritionRemoteDataSource', () {
    test('getMealPlans GETs the meal-plan endpoint and parses pages', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'results': [
                  {
                    'id': 1,
                    'name': 'Cut Plan',
                    'target_calories': 1800,
                    'duration_days': 7,
                    'days': [
                      {'id': 2, 'day_number': 1, 'items': []},
                    ],
                  },
                ],
              }),
        ],
      );
      final source = AiNutritionRemoteDataSource(dio);

      final plans = await source.getMealPlans();

      expect(plans, hasLength(1));
      expect(plans.single.name, 'Cut Plan');
      expect(plans.single.targetCalories, 1800);
      expect(plans.single.durationDays, 7);
      expect(
        (dio.httpClientAdapter as CannedAdapter).recorded.single.uri.path,
        '/ai/nutrition/meal-plan/',
      );
    });

    test('generateMealPlan POSTs preferences and parses the created plan', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(201, {'id': 5, 'name': 'Veg Bulking'}),
        ],
      );
      final source = AiNutritionRemoteDataSource(dio);

      final plan = await source.generateMealPlan({'diet': 'veg', 'calories': 2500});

      expect(plan.id, 5);
      expect(plan.name, 'Veg Bulking');

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.method, 'POST');
      expect(call.recorded.single.uri.path, '/ai/nutrition/meal-plan/generate/');
      expect(call.recorded.single.bodyMap, {'diet': 'veg', 'calories': 2500});
    });

    test('getShoppingList passes the plan id as a query parameter', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'results': [
                  {'id': 1, 'name': 'Oats', 'quantity': 2, 'unit': 'kg', 'is_checked': true},
                  {'id': 2},
                ],
              }),
          () => cannedResponse(200, {'results': []}),
        ],
      );
      final source = AiNutritionRemoteDataSource(dio);

      final items = await source.getShoppingList(planId: 12);

      expect(items, hasLength(2));
      expect(items.first.quantity, 2);
      expect(items.first.isChecked, isTrue);
      expect(items.last.name, 'Item');
      expect(items.last.isChecked, isFalse);

      final calls = (dio.httpClientAdapter as CannedAdapter).recorded;
      expect(calls.first.uri.queryParameters['plan'], '12');

      await source.getShoppingList();
      expect(calls.last.uri.queryParameters.containsKey('plan'), isFalse);
    });

    test('trackMacros POSTs to the track endpoint', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(201, {'ok': true})],
      );
      final source = AiNutritionRemoteDataSource(dio);

      await source.trackMacros({'calories': 1900});

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.method, 'POST');
      expect(call.recorded.single.uri.path, '/ai/nutrition/track/');
      expect(call.recorded.single.bodyMap, {'calories': 1900});
    });

    test('errors map to the matching failures', () async {
      final network = Dio()..httpClientAdapter = CannedAdapter(
        throws: () => DioException(
          requestOptions: RequestOptions(path: '/x'),
          type: DioExceptionType.receiveTimeout,
        ),
      );
      await expectLater(
        AiNutritionRemoteDataSource(network).getMealPlans(),
        throwsA(isA<NetworkFailure>()),
      );

      final validation = Dio()..httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(400, {'calories': ['Too high']})],
      );
      await expectLater(
        AiNutritionRemoteDataSource(validation).generateMealPlan({}),
        throwsA(
          isA<ValidationFailure>()
              .having((f) => f.statusCode, 'statusCode', 400)
              .having((f) => f.errors, 'errors', {'calories': ['Too high']}),
        ),
      );

      final auth = Dio()..httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(402, {'nope': 1})],
      );
      await expectLater(
        AiNutritionRemoteDataSource(auth).trackMacros({}),
        throwsA(
          isA<ServerFailure>().having((f) => f.message, 'message', 'Server error'),
        ),
      );
    });
  });
}