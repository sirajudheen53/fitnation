import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mockito/mockito.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/ai_nutrition/domain/repositories/ai_nutrition_repository.dart';
import 'package:fitnation_app/features/ai_nutrition/models/meal_plan.dart';
import 'package:fitnation_app/features/ai_nutrition/models/meal_plan_item.dart';
import 'package:fitnation_app/features/ai_nutrition/presentation/providers/ai_nutrition_provider.dart';
import 'package:fitnation_app/features/ai_nutrition/presentation/screens/nutrition_screen.dart';

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
    days: [
      MealPlanDay(
        dayNumber: 1,
        items: const [
          MealPlanItem(
            name: 'Oats',
            mealType: 'breakfast',
            calories: 300,
            protein: 12,
          ),
        ],
      ),
    ],
  );

  Widget buildWidget() {
    return ProviderScope(
      overrides: [
        aiNutritionRepositoryProvider.overrideWith((ref) => mockRepo),
        mealPlansProvider.overrideWith((ref) async => [plan]),
        shoppingListProvider.overrideWith((ref, id) async => const []),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const NutritionScreen(),
      ),
    );
  }

  testWidgets('renders meal plan summary', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.text('AI Nutrition'), findsOneWidget);
    expect(find.text('Weight Loss Plan'), findsOneWidget);
    expect(find.text('1800 kcal/day'), findsOneWidget);
    expect(find.text('Daily Macros'), findsOneWidget);
  });

  testWidgets('renders empty state when no plans', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          mealPlansProvider.overrideWith((ref) async => const []),
        ],
        child: MaterialApp(
          theme: AppTheme.light,
          home: const NutritionScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('No meal plan yet'), findsOneWidget);

    // The generate button may be below the fold; scroll to reveal it.
    await tester.scrollUntilVisible(
      find.text('Generate New Plan'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Generate New Plan'), findsOneWidget);
  });
}
