import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import 'package:fitnation_app/features/diet/data/models/diet_plan.dart';
import 'package:fitnation_app/features/diet/data/models/meal.dart';
import 'package:fitnation_app/features/diet/presentation/screens/meal_detail_screen.dart';

void main() {
  const plan = DietPlan(id: 20, name: 'Cut 8 weeks');
  const day = DietDay(
    id: 31,
    name: 'Day 1',
    dayNumber: 1,
    meals: [
      Meal(
        name: 'Lunch',
        mealType: 'lunch',
        foodItems: [
          FoodItem(name: 'Rice', calories: 400),
          FoodItem(name: 'Dal', calories: 200, protein: 12),
        ],
      ),
      Meal(name: 'Snack'),
    ],
  );

  Future<void> pumpScreen(WidgetTester tester) async {
    final router = GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) =>
              const MealDetailScreen(plan: plan, day: day),
        ),
        GoRoute(
          path: '/diet/log',
          builder: (context, state) =>
              const Scaffold(body: Center(child: Text('Log screen'))),
        ),
      ],
    );

    await tester.pumpWidget(MaterialApp.router(routerConfig: router));
    await tester.pumpAndSettle();
  }

  testWidgets('renders the day summary, meals, and foods', (tester) async {
    await pumpScreen(tester);

    expect(find.text('Day 1'), findsOneWidget);
    // 400 (Rice) + 200 (Dal) + 0 (Snack has no items)
    expect(find.text('600'), findsOneWidget);
    expect(find.text('Calories'), findsOneWidget);
    // Food protein: Dal only carries 12 g.
    expect(find.text('12g'), findsOneWidget);
    expect(find.text('Protein'), findsOneWidget);
    expect(find.text('2'), findsOneWidget);
    expect(find.text('Meals'), findsOneWidget);

    expect(find.text('Lunch'), findsOneWidget);
    expect(find.text('lunch'), findsOneWidget);
    expect(find.text('600 kcal'), findsOneWidget);
    expect(find.text('Rice'), findsOneWidget);
    expect(find.text('400 kcal'), findsOneWidget);
    expect(find.text('Dal'), findsOneWidget);
    expect(find.text('200 kcal'), findsOneWidget);

    // The snack has no food items, so the only other total is the snack
    // card's own zero-calorie header.
    expect(find.text('0 kcal'), findsOneWidget);
  });

  testWidgets('the meals without a type or items render without extra rows', (tester) async {
    await pumpScreen(tester);

    expect(find.text('Snack'), findsOneWidget);
    // The snack contributes 0 kcal to the summary and renders its own
    // total; no meal-type line is shown.
    expect(find.text('lunch'), findsOneWidget);
  });

  testWidgets('Log Meals pushes the log screen with plan and day', (tester) async {
    await pumpScreen(tester);

    await tester.tap(find.text('Log Meals'));
    await tester.pumpAndSettle();

    expect(find.text('Log screen'), findsOneWidget);
  });
}