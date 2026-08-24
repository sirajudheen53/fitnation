import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/ai_nutrition/models/meal_plan.dart';
import 'package:fitnation_app/features/ai_nutrition/models/meal_plan_item.dart';
import 'package:fitnation_app/features/ai_nutrition/models/shopping_list_item.dart';

void main() {
  group('MealPlanItem', () {
    test('fromJson parses macros', () {
      final item = MealPlanItem.fromJson({
        'id': 1,
        'name': 'Oats',
        'meal_type': 'breakfast',
        'calories': 300,
        'protein': 12,
        'carbs': 50,
        'fat': 5,
      });

      expect(item.name, 'Oats');
      expect(item.mealType, 'breakfast');
      expect(item.calories, 300);
      expect(item.protein, 12);
    });
  });

  group('MealPlanDay & MealPlan', () {
    test('day totals macros from items', () {
      final day = MealPlanDay(
        dayNumber: 1,
        items: const [
          MealPlanItem(
            name: 'Oats',
            mealType: 'breakfast',
            calories: 300,
            protein: 12,
          ),
          MealPlanItem(
            name: 'Chicken',
            mealType: 'lunch',
            calories: 500,
            protein: 40,
          ),
        ],
      );

      expect(day.totalCalories, 800);
      expect(day.totalProtein, 52);
    });

    test('plan fromJson parses days', () {
      final plan = MealPlan.fromJson({
        'id': 1,
        'name': 'Weight Loss',
        'target_calories': 1800,
        'days': [
          {
            'day_number': 1,
            'items': [
              {'name': 'Oats', 'meal_type': 'breakfast', 'calories': 300},
            ],
          },
        ],
      });

      expect(plan.id, 1);
      expect(plan.targetCalories, 1800);
      expect(plan.days.length, 1);
      expect(plan.days.first.items.length, 1);
    });
  });

  group('ShoppingListItem', () {
    test('fromJson parses item', () {
      final item = ShoppingListItem.fromJson({
        'id': 1,
        'name': 'Oats',
        'quantity': 2,
        'unit': 'kg',
        'is_checked': true,
      });

      expect(item.name, 'Oats');
      expect(item.quantity, 2);
      expect(item.unit, 'kg');
      expect(item.isChecked, isTrue);
    });
  });
}
