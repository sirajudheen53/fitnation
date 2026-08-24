import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/diet/data/models/meal.dart';
import 'package:fitnation_app/features/diet/data/models/diet_plan.dart';
import 'package:fitnation_app/features/diet/presentation/providers/diet_provider.dart';
import 'package:fitnation_app/features/diet/presentation/screens/diet_plan_screen.dart';

void main() {
  final assignment = DietAssignment(
    id: 1,
    customerId: 3,
    planId: 20,
    planName: 'Weight Loss Plan',
    isActive: true,
  );

  final plan = DietPlan(
    id: 20,
    name: 'Weight Loss Plan',
    targetCalories: 1800,
    durationWeeks: 4,
    days: [
      DietDay(
        id: 1,
        name: 'Day 1',
        dayNumber: 1,
        meals: [
          Meal(
            id: 1,
            name: 'Breakfast',
            mealType: 'breakfast',
            foodItems: [
              const FoodItem(id: 1, name: 'Oats', calories: 150, protein: 5.0),
            ],
          ),
        ],
      ),
    ],
  );

  Widget buildWidget() {
    return ProviderScope(
      overrides: [
        activeDietAssignmentProvider.overrideWith((ref) async => assignment),
        dietPlanProvider.overrideWith((ref, planId) async => plan),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const DietPlanScreen(),
      ),
    );
  }

  testWidgets('renders plan name and meal days', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.text('Weight Loss Plan'), findsOneWidget);
    expect(find.text('Meal Days'), findsOneWidget);
    expect(find.text('Day 1'), findsOneWidget);
    expect(find.textContaining('1 meals'), findsOneWidget);
  });

  testWidgets('renders empty state when no assignment', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          activeDietAssignmentProvider.overrideWith((ref) async => null),
        ],
        child: MaterialApp(
          theme: AppTheme.light,
          home: const DietPlanScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('No active diet plan'), findsOneWidget);
  });
}
