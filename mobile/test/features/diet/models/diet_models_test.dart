import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/diet/data/models/diet_plan.dart';
import 'package:fitnation_app/features/diet/data/models/meal.dart';

void main() {
  group('FoodItem', () {
    test('parses a full item and round-trips', () {
      const item = FoodItem(
        id: 2,
        name: 'Oats',
        calories: 380,
        protein: 13,
        carbs: 67,
        fat: 7,
        quantity: 80,
        unit: 'g',
        servingSize: '1 bowl',
      );

      final json = item.toJson();
      final reparsed = FoodItem.fromJson(json);
      expect(reparsed.name, 'Oats');
      expect(reparsed.calories, 380);
      expect(reparsed.quantity, 80);
      expect(reparsed.servingSize, '1 bowl');
    });

    test('degrades a missing name and omits nulls in toJson', () {
      final item = FoodItem.fromJson({});
      expect(item.name, 'Food');
      expect(item.toJson(), {'name': 'Food'});
    });
  });

  group('Meal', () {
    const meal = Meal(
      name: 'Breakfast',
      mealType: 'breakfast',
      foodItems: [
        FoodItem(name: 'Oats', calories: 380, protein: 13),
        FoodItem(name: 'Milk', calories: 150, protein: 8),
      ],
    );

    test('parses with food items', () {
      final parsed = Meal.fromJson(meal.toJson());
      expect(parsed.name, 'Breakfast');
      expect(parsed.foodItems, hasLength(2));
      expect(parsed.totalCalories, 530);
      expect(parsed.totalProtein, 21);
    });

    test('degrades missing names and defaults isCompleted to false', () {
      final parsed = Meal.fromJson({'food_items': []});
      expect(parsed.name, 'Meal');
      expect(parsed.isCompleted, isFalse);
    });

    test('totals ignore items without macros', () {
      const empty = Meal(name: 'Snack');
      expect(empty.totalCalories, 0);
      const nullish = Meal(name: 'Snack', foodItems: [FoodItem(name: 'X')]);
      expect(nullish.totalCalories, 0);
      expect(nullish.totalProtein, 0);
    });

    test('copyWith only changes isCompleted', () {
      final completed = meal.copyWith(isCompleted: true);
      expect(completed.isCompleted, isTrue);
      expect(completed.name, meal.name);
      expect(completed.foodItems, meal.foodItems);
      expect(meal.copyWith().isCompleted, isFalse);
    });
  });

  group('DietDay', () {
    test('parses days with meals and sums macros', () {
      final day = DietDay.fromJson({
        'id': 1,
        'day_number': 2,
        'meals': [
          {
            'name': 'Lunch',
            'food_items': [
              {'name': 'Rice', 'calories': 400, 'protein': 10},
              {'name': 'Dal', 'calories': 200, 'protein': 12},
            ],
          },
          {
            'name': 'Dinner',
            'food_items': [
              {'name': 'Salad', 'calories': 150, 'protein': 5},
            ],
          },
        ],
      });

      expect(day.id, 1);
      expect(day.dayNumber, 2);
      expect(day.meals, hasLength(2));
      expect(day.totalCalories, 750);
      expect(day.totalProtein, 27);
    });

    test('defaults name to Day when missing', () {
      expect(DietDay.fromJson({}).name, 'Day');
      expect(DietDay.fromJson({}).meals, isEmpty);
    });

    test('round-trips through toJson', () {
      const day = DietDay(name: 'Day 1', meals: [Meal(name: 'Lunch')]);
      final reparsed = DietDay.fromJson(day.toJson());
      expect(reparsed.name, 'Day 1');
      expect(reparsed.meals, hasLength(1));
      expect(reparsed.totalCalories, 0);
    });
  });

  group('DietPlan', () {
    test('parses a full plan and round-trips', () {
      final plan = DietPlan.fromJson({
        'id': 1,
        'name': 'Cut 8 weeks',
        'description': 'Moderate deficit',
        'duration_weeks': 8,
        'meals_per_day': 4,
        'target_calories': 1800,
        'days': [
          {'id': 1, 'name': 'Day 1', 'meals': []},
        ],
      });

      expect(plan.id, 1);
      expect(plan.name, 'Cut 8 weeks');
      expect(plan.durationWeeks, 8);
      expect(plan.mealsPerDay, 4);
      expect(plan.targetCalories, 1800);
      expect(plan.days, hasLength(1));

      final reparsed = DietPlan.fromJson(plan.toJson());
      expect(reparsed.durationWeeks, 8);
      expect(reparsed.days, hasLength(1));
    });

    test('defaults the name and tolerates missing days', () {
      expect(DietPlan.fromJson({'id': 2}).name, 'Diet Plan');
      expect(DietPlan.fromJson({'id': 2}).days, isEmpty);
    });
  });

  group('DietAssignment', () {
    test('parses the canonical and alias payload keys', () {
      final a = DietAssignment.fromJson({
        'id': 1,
        'customer': 10,
        'plan': 20,
        'plan_name': 'Cut 8 weeks',
        'is_active': true,
        'assigned_at': '2026-06-01T00:00:00Z',
      });
      final b = DietAssignment.fromJson({
        'id': 2,
        'customer_id': 11,
        'plan_id': 21,
        'start_date': '2026-06-02T00:00:00Z',
        'end_date': '2026-07-02T00:00:00Z',
      });

      expect(a.customerId, 10);
      expect(a.planId, 20);
      expect(a.assignedAt, DateTime.parse('2026-06-01T00:00:00Z'));
      expect(b.customerId, 11);
      expect(b.startDate, DateTime.parse('2026-06-02T00:00:00Z'));
      expect(b.endDate, DateTime.parse('2026-07-02T00:00:00Z'));
    });

    test('degrades missing customer/plan to 0 and defaults is_active', () {
      final a = DietAssignment.fromJson({'id': 1});
      expect(a.customerId, 0);
      expect(a.planId, 0);
      expect(a.isActive, isTrue);
    });

    test('toJson writes the canonical keys only', () {
      const a = DietAssignment(
        id: 3,
        customerId: 10,
        planId: 20,
        planName: 'Cut',
        isActive: false,
      );
      final json = a.toJson();
      expect(json, {
        'id': 3,
        'customer': 10,
        'plan': 20,
        'plan_name': 'Cut',
        'is_active': false,
      });
      expect(json.containsKey('assigned_at'), isFalse);
    });
  });
}