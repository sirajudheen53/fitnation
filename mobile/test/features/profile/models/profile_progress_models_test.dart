import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/profile/data/models/customer_profile.dart';
import 'package:fitnation_app/features/progress/data/models/body_measurement.dart';

void main() {
  group('CustomerProfile', () {
    test('fromJson parses backend snake_case fields', () {
      final json = {
        'id': 3,
        'name': 'Raman Nair',
        'email': 'raman@example.com',
        'phone': '+919876543210',
        'emergency_contact_name': 'Priya Nair',
        'emergency_contact_phone': '+919876543211',
        'address_street': '12 MG Road',
        'address_city': 'Kochi',
        'address_state': 'Kerala',
        'address_postal_code': '682001',
        'is_active': true,
      };

      final profile = CustomerProfile.fromJson(json);

      expect(profile.id, 3);
      expect(profile.fullName, 'Raman Nair');
      expect(profile.emergencyContact, 'Priya Nair');
      expect(profile.emergencyPhone, '+919876543211');
      expect(profile.fullAddress, '12 MG Road, Kochi, Kerala, 682001');
      expect(profile.isActive, true);
    });

    test('fullName falls back to first/last name', () {
      const profile = CustomerProfile(
        id: 1,
        firstName: 'Raman',
        lastName: 'Nair',
      );
      expect(profile.fullName, 'Raman Nair');
    });
  });

  group('HealthProfile', () {
    test('fromJson parses height_cm/weight_kg and list fields', () {
      final json = {
        'id': 1,
        'height_cm': 175.0,
        'weight_kg': 75.5,
        'bmi': 24.6,
        'blood_group': 'O+',
        'medical_conditions': ['Asthma', 'None'],
        'allergies': ['Peanuts'],
      };

      final health = HealthProfile.fromJson(json);

      expect(health.height, 175.0);
      expect(health.weight, 75.5);
      expect(health.bmi, 24.6);
      expect(health.bloodGroup, 'O+');
      expect(health.medicalConditions, 'Asthma, None');
      expect(health.allergies, 'Peanuts');
    });
  });

  group('BodyMeasurement', () {
    test('fromJson parses date_logged and weight_kg', () {
      final json = {
        'id': 1,
        'date_logged': '2026-08-24',
        'weight_kg': 75.5,
        'body_fat_percentage': 18.0,
      };

      final measurement = BodyMeasurement.fromJson(json);

      expect(measurement.id, 1);
      expect(measurement.measuredAt, isNotNull);
      expect(measurement.weight, 75.5);
      expect(measurement.bodyFat, 18.0);
    });
  });

  group('FitnessGoal', () {
    test('fromJson parses progress fields', () {
      final json = {
        'id': 1,
        'goal_type': 'lose_weight',
        'is_active': true,
        'status': 'active',
        'target_value': 70.0,
        'target_unit': 'kg',
        'current_value': 75.5,
        'progress_percentage': 45.0,
      };

      final goal = FitnessGoal.fromJson(json);

      expect(goal.id, 1);
      expect(goal.goalType, 'lose_weight');
      expect(goal.targetValue, 70.0);
      expect(goal.targetUnit, 'kg');
      expect(goal.currentValue, 75.5);
      expect(goal.progressPercentage, 45.0);
      expect(goal.isActive, true);
    });
  });
}
