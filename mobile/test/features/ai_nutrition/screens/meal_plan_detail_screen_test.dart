import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mockito/mockito.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/ai_nutrition/domain/repositories/ai_nutrition_repository.dart';
import 'package:fitnation_app/features/ai_nutrition/models/meal_plan.dart';
import 'package:fitnation_app/features/ai_nutrition/models/meal_plan_item.dart';
import 'package:fitnation_app/features/ai_nutrition/models/shopping_list_item.dart';
import 'package:fitnation_app/features/ai_nutrition/presentation/providers/ai_nutrition_provider.dart';
import 'package:fitnation_app/features/ai_nutrition/presentation/screens/meal_plan_detail_screen.dart';

class MockAiNutritionRepository extends Mock implements AiNutritionRepository {}

void main() {
  late MockAiNutritionRepository mockRepo;

  setUp(() {
    mockRepo = MockAiNutritionRepository();
  });

  final plan = MealPlan(
    id: 1,
    name: 'Weight Loss Plan',
    description: 'AI generated plan',
    targetCalories: 1800,
    durationDays: 7,
    days: [
      MealPlanDay(
        dayNumber: 1,
        items: const [
          MealPlanItem(
            name: 'Oats',
            mealType: 'breakfast',
            calories: 300,
            protein: 12,
            carbs: 50,
            fat: 5,
          ),
          MealPlanItem(
            name: 'Grilled Chicken',
            mealType: 'lunch',
            calories: 500,
            protein: 40,
          ),
        ],
      ),
    ],
  );

  Widget buildWidget() {
    return ProviderScope(
      overrides: [
        aiNutritionRepositoryProvider.overrideWith((ref) => mockRepo),
        shoppingListProvider.overrideWith((ref, id) async => const [
              ShoppingListItem(
                id: 1,
                name: 'Oats',
                quantity: 2,
                unit: 'kg',
              ),
            ]),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: MealPlanDetailScreen(plan: plan),
      ),
    );
  }

  testWidgets('renders 7-day plan with meals', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.text('Weight Loss Plan'), findsOneWidget);
    expect(find.text('Day 1'), findsOneWidget);
    expect(find.text('Grilled Chicken'), findsOneWidget);
    // Oats appears in both the day meal and the shopping list.
    expect(find.text('Oats'), findsWidgets);
  });

  testWidgets('renders macro chips per day', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    // Total protein for day 1 = 12 + 40 = 52g
    expect(find.text('Protein 52g'), findsOneWidget);
  });

  testWidgets('renders shopping list items', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.text('Shopping List'), findsWidgets);
    expect(find.text('Oats'), findsWidgets);
  });
}
