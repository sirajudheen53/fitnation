import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/ai_nutrition/data/data_sources/ai_nutrition_remote_data_source.dart';
import 'package:fitnation_app/features/ai_nutrition/domain/repositories/ai_nutrition_repository.dart';
import '../../../helpers/canned_adapter.dart';

void main() {
  AiNutritionRepository repo(CannedAdapter adapter) {
    final dio = Dio()..httpClientAdapter = adapter;
    return AiNutritionRepository(AiNutritionRemoteDataSource(dio));
  }

  test('getMealPlans returns the plans, or null with the failure', () async {
    final ok = repo(CannedAdapter(
      calls: [
        () => cannedResponse(200, {'results': [{'id': 1, 'name': 'Cut Plan'}]}),
      ],
    ));
    final (:plans, :error) = await ok.getMealPlans();
    expect(plans!.single.name, 'Cut Plan');
    expect(error, isNull);

    final down = repo(CannedAdapter(
      calls: [() => cannedResponse(500, {'detail': 'AI backend down'})],
    ));
    final (plans: none, error: failure) = await down.getMealPlans();
    expect(none, isNull);
    expect(failure, isA<ServerFailure>());
  });

  test('generateMealPlan posts preferences and parses the plan', () async {
    final ok = repo(CannedAdapter(
      calls: [() => cannedResponse(201, {'id': 5, 'name': 'Veg Bulking'})],
    ));
    final (:plan, :error) = await ok.generateMealPlan({'diet': 'veg'});
    expect(plan!.id, 5);
    expect(error, isNull);

    final rejected = repo(CannedAdapter(
      calls: [() => cannedResponse(400, {'diet': ['Unsupported diet']})],
    ));
    final (plan: blocked, error: rejectError) = await rejected.generateMealPlan({});
    expect(blocked, isNull);
    expect(rejectError, isA<ValidationFailure>());
  });

  test('getShoppingList forwards the plan id', () async {
    final ok = repo(CannedAdapter(
      calls: [
        () => cannedResponse(200, {
              'results': [
                {'id': 1, 'name': 'Oats', 'quantity': 2, 'is_checked': true},
              ],
            }),
      ],
    ));
    final (:items, :error) = await ok.getShoppingList(planId: 12);
    expect(items!.single.name, 'Oats');
    expect(error, isNull);

    final down = repo(CannedAdapter(
      calls: [() => cannedResponse(500, {'detail': 'x'})],
    ));
    final (items: none, error: failure) = await down.getShoppingList();
    expect(none, isNull);
    expect(failure, isA<ServerFailure>());
  });

  test('trackMacros reports success, or the failure', () async {
    final ok = repo(CannedAdapter(
      calls: [() => cannedResponse(201, {'ok': true})],
    ));
    final (success: saved, error: okError) = await ok.trackMacros({'calories': 1900});
    expect(saved, isTrue);
    expect(okError, isNull);

    final down = repo(CannedAdapter(
      calls: [() => cannedResponse(503, {'detail': 'maintenance'})],
    ));
    final (success: lost, error: failError) = await down.trackMacros({});
    expect(lost, isFalse);
    expect(failError, isA<ServerFailure>());
  });
}