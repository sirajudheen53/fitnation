import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/plans/data/models/diet_assignment_model.dart';
import 'package:fitnation_app/features/plans/data/models/workout_assignment_model.dart';

/// Payload shape produced by the #90 assignment serializers.
Map<String, dynamic> workoutAssignmentJson({int id = 11}) => {
      'id': id,
      'customer': 42,
      'workout_plan': 7,
      'workout_plan_name': 'Beginner Strength',
      'customer_name': 'Arjun Nair',
      'customer_is_deleted': false,
      'start_date': '2026-10-01',
      'end_date': null,
      'is_active': true,
      'assigned_by': 3,
      'notes': 'Focus on form for the first two weeks.',
      'created_at': '2026-10-01T09:15:00Z',
      'updated_at': '2026-10-05T18:40:00Z',
    };

Map<String, dynamic> dietAssignmentJson({int id = 21}) => {
      'id': id,
      'customer': 42,
      'diet_plan': 9,
      'diet_plan_name': 'High Protein Cut',
      'customer_name': 'Arjun Nair',
      'customer_is_deleted': false,
      'start_date': '2026-10-02',
      'end_date': '2026-12-02',
      'is_active': true,
      'assigned_by': 3,
      'notes': null,
      'created_at': '2026-10-02T08:00:00Z',
      'updated_at': '2026-10-02T08:00:00Z',
    };

void main() {
  group('WorkoutAssignmentModel', () {
    test('parses the active-assignment payload', () {
      final model = WorkoutAssignmentModel.fromJson(workoutAssignmentJson());

      expect(model.id, 11);
      expect(model.customer, 42);
      expect(model.workoutPlan, 7);
      expect(model.workoutPlanName, 'Beginner Strength');
      expect(model.customerName, 'Arjun Nair');
      expect(model.customerIsDeleted, isFalse);
      expect(model.startDate, DateTime(2026, 10, 1));
      expect(model.endDate, isNull);
      expect(model.isActive, isTrue);
      expect(model.assignedBy, 3);
      expect(model.notes, 'Focus on form for the first two weeks.');
      expect(model.createdAt, DateTime.utc(2026, 10, 1, 9, 15));
      expect(model.updatedAt, DateTime.utc(2026, 10, 5, 18, 40));
    });

    test('round-trips through toJson', () {
      final model =
          WorkoutAssignmentModel.fromJson(workoutAssignmentJson(id: 12));
      final restored =
          WorkoutAssignmentModel.fromJson(model.toJson()..['id'] = 12);

      expect(restored.id, model.id);
      expect(restored.workoutPlanName, model.workoutPlanName);
      expect(restored.startDate, model.startDate);
      expect(restored.endDate, model.endDate);
      expect(restored.notes, model.notes);
    });

    test('defaults optional flags and treats null dates/notes', () {
      final json = workoutAssignmentJson()
        ..remove('customer_is_deleted')
        ..remove('is_active')
        ..remove('assigned_by')
        ..remove('notes');
      final model = WorkoutAssignmentModel.fromJson(json);

      expect(model.customerIsDeleted, isFalse);
      expect(model.isActive, isFalse);
      expect(model.assignedBy, isNull);
      expect(model.notes, isNull);
    });

    test('equality is by id', () {
      final a = WorkoutAssignmentModel.fromJson(workoutAssignmentJson());
      final b = WorkoutAssignmentModel.fromJson(workoutAssignmentJson());
      final c = WorkoutAssignmentModel.fromJson(workoutAssignmentJson(id: 99));

      expect(a, equals(b));
      expect(a, isNot(equals(c)));
      expect(a.hashCode, b.hashCode);
    });
  });

  group('DietAssignmentModel', () {
    test('parses the active-assignment payload including an end date', () {
      final model = DietAssignmentModel.fromJson(dietAssignmentJson());

      expect(model.id, 21);
      expect(model.customer, 42);
      expect(model.dietPlan, 9);
      expect(model.dietPlanName, 'High Protein Cut');
      expect(model.startDate, DateTime(2026, 10, 2));
      expect(model.endDate, DateTime(2026, 12, 2));
      expect(model.isActive, isTrue);
      expect(model.notes, isNull);
    });

    test('round-trips through toJson', () {
      final model = DietAssignmentModel.fromJson(dietAssignmentJson(id: 22));
      final restored =
          DietAssignmentModel.fromJson(model.toJson()..['id'] = 22);

      expect(restored.id, model.id);
      expect(restored.dietPlanName, model.dietPlanName);
      expect(restored.startDate, model.startDate);
      expect(restored.endDate, model.endDate);
    });

    test('equality is by id', () {
      final a = DietAssignmentModel.fromJson(dietAssignmentJson());
      final b = DietAssignmentModel.fromJson(dietAssignmentJson());

      expect(a, equals(b));
      expect(a.hashCode, b.hashCode);
    });
  });
}
