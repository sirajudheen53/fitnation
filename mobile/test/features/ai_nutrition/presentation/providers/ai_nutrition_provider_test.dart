import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/ai_nutrition/domain/repositories/ai_nutrition_repository.dart';
import 'package:fitnation_app/features/ai_nutrition/models/meal_plan.dart';
import 'package:fitnation_app/features/ai_nutrition/models/shopping_list_item.dart';
import 'package:fitnation_app/features/ai_nutrition/presentation/providers/ai_nutrition_provider.dart';

class _CannedRepository implements AiNutritionRepository {
  _CannedRepository({
    this.plansResult,
    this.generateResult,
    this.shoppingResult,
    this.macrosResult,
  });

  final (List<MealPlan>?, Failure?)? plansResult;
  final (MealPlan?, Failure?)? generateResult;
  final (List<ShoppingListItem>?, Failure?)? shoppingResult;
  final (bool, Failure?)? macrosResult;

  @override
  Future<({List<MealPlan>? plans, Failure? error})> getMealPlans() async {
    final canned = plansResult!;
    return (plans: canned.$1, error: canned.$2);
  }

  @override
  Future<({MealPlan? plan, Failure? error})> generateMealPlan(
    Map<String, dynamic> preferences,
  ) async {
    final canned = generateResult!;
    return (plan: canned.$1, error: canned.$2);
  }

  @override
  Future<({List<ShoppingListItem>? items, Failure? error})> getShoppingList({
    int? planId,
  }) async {
    final canned = shoppingResult!;
    return (items: canned.$1, error: canned.$2);
  }

  @override
  Future<({bool success, Failure? error})> trackMacros(
    Map<String, dynamic> data,
  ) async {
    final canned = macrosResult!;
    return (success: canned.$1, error: canned.$2);
  }
}

const _plan = MealPlan(id: 1, name: 'Cut Plan');

void main() {
  ProviderContainer container(_CannedRepository repo) {
    final c = ProviderContainer(overrides: [
      aiNutritionRepositoryProvider.overrideWithValue(repo),
    ]);
    addTearDown(c.dispose);
    return c;
  }

  group('mealPlansProvider', () {
    test('surfaces the plans', () async {
      final c = container(_CannedRepository(
        plansResult: (const [_plan], null),
      ));
      expect((await c.read(mealPlansProvider.future)).single.name, 'Cut Plan');
    });

    test('throws the failure so the UI can show an error state', () async {
      final c = container(_CannedRepository(
        plansResult: (null, const ServerFailure(message: 'AI backend down')),
      ));
      await expectLater(
        c.read(mealPlansProvider.future),
        throwsA(isA<ServerFailure>()),
      );
    });
  });

  group('shoppingListProvider', () {
    test('surfaces the items', () async {
      final c = container(_CannedRepository(
        shoppingResult: (const <ShoppingListItem>[], null),
      ));
      expect(await c.read(shoppingListProvider(12).future), isEmpty);
    });

    test('throws the failure', () async {
      final c = container(_CannedRepository(
        shoppingResult: (null, const NetworkFailure()),
      ));
      await expectLater(
        c.read(shoppingListProvider(null).future),
        throwsA(isA<NetworkFailure>()),
      );
    });
  });

  group('GenerateNotifier.generate', () {
    test('stores the generated plan and stops loading on success', () async {
      final c = container(_CannedRepository(
        generateResult: (_plan, null),
      ));
      final notifier = c.read(generatePlanProvider.notifier);

      final plan = await notifier.generate({'goal': 'weight_loss'});

      expect(plan!.name, 'Cut Plan');
      final state = c.read(generatePlanProvider);
      expect(state.isLoading, isFalse);
      expect(state.generatedPlan!.id, 1);
      expect(state.errorMessage, isNull);
    });

    test('exposes the error and returns null on failure', () async {
      final c = container(_CannedRepository(
        generateResult: (null, const ServerFailure(message: 'AI backend down')),
      ));
      final notifier = c.read(generatePlanProvider.notifier);

      final plan = await notifier.generate({'goal': 'weight_loss'});

      expect(plan, isNull);
      final state = c.read(generatePlanProvider);
      expect(state.isLoading, isFalse);
      expect(state.generatedPlan, isNull);
      expect(state.errorMessage, 'AI backend down');
    });

    test('reset clears the generated plan and any error', () async {
      final c = container(_CannedRepository(
        generateResult: (_plan, null),
      ));
      final notifier = c.read(generatePlanProvider.notifier);
      await notifier.generate({});

      notifier.reset();

      expect(c.read(generatePlanProvider), const GenerateState());
    });
  });
}