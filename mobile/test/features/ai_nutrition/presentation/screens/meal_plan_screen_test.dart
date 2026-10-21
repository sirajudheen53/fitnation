import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/ai_nutrition/domain/repositories/ai_nutrition_repository.dart';
import 'package:fitnation_app/features/ai_nutrition/models/meal_plan.dart';
import 'package:fitnation_app/features/ai_nutrition/models/meal_plan_item.dart';
import 'package:fitnation_app/features/ai_nutrition/models/shopping_list_item.dart';
import 'package:fitnation_app/features/ai_nutrition/presentation/providers/ai_nutrition_provider.dart';
import 'package:fitnation_app/features/ai_nutrition/presentation/screens/meal_plan_screen.dart';

/// Repository that serves canned results without a network.
class _CannedRepository implements AiNutritionRepository {
  _CannedRepository({this.generateResult});

  final (MealPlan?, Failure?)? generateResult;

  @override
  Future<({List<MealPlan>? plans, Failure? error})> getMealPlans() async {
    return (plans: null, error: const ServerFailure(message: 'unused'));
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
    return (items: null, error: const ServerFailure(message: 'unused'));
  }

  @override
  Future<({bool success, Failure? error})> trackMacros(
    Map<String, dynamic> data,
  ) async {
    return (success: false, error: const ServerFailure(message: 'unused'));
  }
}

void main() {
  const plan = MealPlan(
    id: 1,
    name: 'Cut Plan',
    targetCalories: 1800,
    days: [
      MealPlanDay(
        dayNumber: 1,
        items: [
          MealPlanItem(name: 'Oats', mealType: 'breakfast', calories: 300, protein: 12),
        ],
      ),
    ],
  );

  Future<void> pumpScreen(
    WidgetTester tester, {
    AiNutritionRepository? repository,
  }) async {
    final router = GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const MealPlanScreen(),
        ),
        GoRoute(
          path: '/nutrition',
          builder: (context, state) =>
              const Scaffold(body: Center(child: Text('Nutrition Home'))),
        ),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          aiNutritionRepositoryProvider.overrideWithValue(
            repository ?? _CannedRepository(),
          ),
        ],
        child: MaterialApp.router(routerConfig: router, theme: AppTheme.light),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('renders the preference rows and the empty grid', (tester) async {
    await pumpScreen(tester);

    expect(find.text('AI Meal Plan'), findsOneWidget);
    expect(find.text('Your preferences'), findsOneWidget);
    expect(find.text('Weight loss'), findsOneWidget);
    expect(find.text('Balanced'), findsOneWidget);
    expect(find.text('2000 kcal'), findsOneWidget);
    expect(find.text('3'), findsOneWidget);
    expect(find.text('7-Day Overview'), findsOneWidget);
    expect(find.text('No plan yet'), findsOneWidget);
    expect(find.text('Set your preferences and tap Generate.'), findsOneWidget);
    expect(find.text('Edit'), findsOneWidget);
    expect(find.text('Generate'), findsOneWidget);
  });

  testWidgets('the preferences sheet applies the chosen values', (tester) async {
    await pumpScreen(tester);

    await tester.tap(find.text('Edit'));
    await tester.pumpAndSettle();
    expect(find.text('Meal Plan Preferences'), findsOneWidget);

    // The duplicated labels on the sheet and the screen make the dropdowns
    // ambiguous — target them by widget type and index instead.
    await tester.tap(find.byType(DropdownButtonFormField<String>).first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Muscle gain').last);
    await tester.pumpAndSettle();

    await tester.tap(find.byType(DropdownButtonFormField<String>).at(1));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Keto').last);
    await tester.pumpAndSettle();

    await tester.tap(find.text('Apply'));
    await tester.pumpAndSettle();

    expect(find.text('Muscle gain'), findsOneWidget);
    expect(find.text('Keto'), findsOneWidget);
  });

  testWidgets('generating a plan shows the confirmation and navigates home', (tester) async {
    await pumpScreen(
      tester,
      repository: _CannedRepository(generateResult: (plan, null)),
    );

    await tester.tap(find.text('Generate'));
    await tester.pumpAndSettle();

    expect(find.byType(SnackBar), findsOneWidget);
    expect(find.text('Meal plan generated!'), findsOneWidget);
    expect(find.text('Nutrition Home'), findsOneWidget);
  });

  testWidgets('a failed generation shows the error inline', (tester) async {
    await pumpScreen(
      tester,
      repository: _CannedRepository(
        generateResult: (null, const ServerFailure(message: 'AI backend down')),
      ),
    );

    await tester.tap(find.text('Generate'));
    await tester.pumpAndSettle();

    expect(find.text('AI backend down'), findsOneWidget);
    expect(find.byType(SnackBar), findsNothing);
    // The screen stays put on failure.
    expect(find.text('Generate'), findsOneWidget);
  });
}