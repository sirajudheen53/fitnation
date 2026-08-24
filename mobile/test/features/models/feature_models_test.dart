import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/diet/data/models/meal.dart';
import 'package:fitnation_app/features/diet/data/models/diet_plan.dart';
import 'package:fitnation_app/features/attendance/data/models/attendance_record.dart';
import 'package:fitnation_app/features/progress/data/models/body_measurement.dart';
import 'package:fitnation_app/features/profile/data/models/customer_profile.dart';
import 'package:fitnation_app/features/feedback/data/models/feedback.dart';

void main() {
  group('FoodItem & Meal', () {
    test('Meal fromJson parses food items', () {
      final json = {
        'id': 1,
        'name': 'Breakfast',
        'meal_type': 'breakfast',
        'food_items': [
          {'id': 1, 'name': 'Oats', 'calories': 150, 'protein': 5.0},
          {'id': 2, 'name': 'Milk', 'calories': 100, 'protein': 8.0},
        ],
      };

      final meal = Meal.fromJson(json);

      expect(meal.name, 'Breakfast');
      expect(meal.foodItems.length, 2);
      expect(meal.totalCalories, 250);
      expect(meal.totalProtein, 13.0);
    });
  });

  group('DietPlan', () {
    test('fromJson parses plan with days and meals', () {
      final json = {
        'id': 1,
        'name': 'Weight Loss Plan',
        'target_calories': 1800,
        'days': [
          {
            'id': 1,
            'name': 'Day 1',
            'meals': [
              {
                'id': 1,
                'name': 'Breakfast',
                'food_items': [
                  {'name': 'Oats', 'calories': 150},
                ],
              },
            ],
          },
        ],
      };

      final plan = DietPlan.fromJson(json);

      expect(plan.id, 1);
      expect(plan.targetCalories, 1800);
      expect(plan.days.length, 1);
      expect(plan.days.first.meals.length, 1);
    });
  });

  group('AttendanceRecord', () {
    test('fromJson parses record', () {
      final json = {
        'id': 1,
        'customer': 3,
        'check_in_time': '2026-08-24T09:00:00Z',
        'status': 'present',
      };

      final record = AttendanceRecord.fromJson(json);

      expect(record.id, 1);
      expect(record.customerId, 3);
      expect(record.checkInTime, isNotNull);
      expect(record.status, 'present');
    });
  });

  group('BodyMeasurement', () {
    test('fromJson parses measurements', () {
      final json = {
        'id': 1,
        'weight': 75.5,
        'height': 175.0,
        'bmi': 24.6,
        'body_fat': 18.0,
      };

      final measurement = BodyMeasurement.fromJson(json);

      expect(measurement.id, 1);
      expect(measurement.weight, 75.5);
      expect(measurement.bmi, 24.6);
    });
  });

  group('CustomerProfile', () {
    test('fromJson parses profile and fullName', () {
      final json = {
        'id': 3,
        'first_name': 'Raman',
        'last_name': 'Nair',
        'email': 'raman@example.com',
        'phone': '+919876543210',
      };

      final profile = CustomerProfile.fromJson(json);

      expect(profile.id, 3);
      expect(profile.fullName, 'Raman Nair');
      expect(profile.phone, '+919876543210');
    });
  });

  group('Feedback', () {
    test('toJson produces correct payload', () {
      const feedback = Feedback(
        customerId: 3,
        subject: 'Great gym',
        message: 'Loved the equipment',
        rating: 5,
        category: 'Facilities',
      );

      final json = feedback.toJson();

      expect(json['customer'], 3);
      expect(json['subject'], 'Great gym');
      expect(json['message'], 'Loved the equipment');
      expect(json['rating'], 5);
      expect(json['category'], 'Facilities');
    });
  });
}
