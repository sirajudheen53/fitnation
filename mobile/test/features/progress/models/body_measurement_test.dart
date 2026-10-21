import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/progress/data/models/body_measurement.dart';

void main() {
  group('BodyMeasurement.fromJson', () {
    test('parses the canonical suffixed keys', () {
      final m = BodyMeasurement.fromJson({
        'id': 11,
        'date_logged': '2026-05-01T10:00:00Z',
        'weight_kg': 72.4,
        'height_cm': 175.0,
        'bmi': 23.6,
        'body_fat_percentage': 18.5,
        'chest_cm': 98.0,
        'waist_cm': 81.0,
        'hips_cm': 96.0,
        'arms_cm': 33.0,
        'thighs_cm': 55.0,
      });

      expect(m.id, 11);
      expect(m.measuredAt, DateTime.parse('2026-05-01T10:00:00Z'));
      expect(m.weight, 72.4);
      expect(m.height, 175.0);
      expect(m.bmi, 23.6);
      expect(m.bodyFat, 18.5);
      expect(m.chest, 98.0);
      expect(m.waist, 81.0);
      expect(m.hips, 96.0);
      expect(m.arms, 33.0);
      expect(m.thighs, 55.0);
    });

    test('accepts the unsuffixed aliases', () {
      final m = BodyMeasurement.fromJson({
        'id': 1,
        'measured_at': '2026-05-02T00:00:00Z',
        'weight': 70,
        'height': 174,
        'body_fat': 17,
        'chest': 97,
        'waist': 80,
        'hips': 95,
        'arms': 32,
        'thighs': 54,
      });

      expect(m.measuredAt, DateTime.parse('2026-05-02T00:00:00Z'));
      expect(m.weight, 70.0);
      expect(m.height, 174.0);
      expect(m.bodyFat, 17.0);
      expect(m.chest, 97.0);
      expect(m.thighs, 54.0);
    });

    test('date_logged wins over measured_at and both can be absent', () {
      final withBoth = BodyMeasurement.fromJson({
        'id': 1,
        'date_logged': '2026-05-01T00:00:00Z',
        'measured_at': '2026-05-02T00:00:00Z',
      });
      expect(withBoth.measuredAt, DateTime.parse('2026-05-01T00:00:00Z'));
      expect(BodyMeasurement.fromJson({'id': 1}).measuredAt, isNull);
    });

    test('toJson round-trips and omits nulls', () {
      const m = BodyMeasurement(id: 12, weight: 72.0, bmi: 23.0);
      final json = m.toJson();
      expect(json.containsKey('height'), isFalse);
      final reparsed = BodyMeasurement.fromJson(json);
      expect(reparsed.weight, m.weight);
      expect(reparsed.bmi, m.bmi);
    });
  });

  group('FitnessGoal', () {
    test('parses a full goal', () {
      final goal = FitnessGoal.fromJson({
        'id': 3,
        'goal_type': 'weight_loss',
        'description': 'Lose 8 kg',
        'target_weight': 68.0,
        'target_date': '2026-12-31T00:00:00Z',
        'status': 'in_progress',
        'is_active': true,
        'target_value': 68.0,
        'target_unit': 'kg',
        'current_value': 74.5,
        'progress_percentage': 35.0,
        'notes': 'weekly check-ins',
      });

      expect(goal.id, 3);
      expect(goal.goalType, 'weight_loss');
      expect(goal.description, 'Lose 8 kg');
      expect(goal.targetWeight, 68.0);
      expect(goal.targetDate, DateTime.parse('2026-12-31T00:00:00Z'));
      expect(goal.status, 'in_progress');
      expect(goal.isActive, isTrue);
      expect(goal.targetUnit, 'kg');
      expect(goal.currentValue, 74.5);
      expect(goal.progressPercentage, 35.0);
    });

    test('description falls back to notes', () {
      final goal = FitnessGoal.fromJson({'id': 1, 'notes': 'aspirational'});
      expect(goal.description, 'aspirational');
      expect(goal.notes, 'aspirational');
    });

    test('is_active defaults to true', () {
      expect(FitnessGoal.fromJson({'id': 1}).isActive, isTrue);
    });

    test('toJson round-trips and omits nulls', () {
      const goal = FitnessGoal(id: 4, status: 'paused', isActive: false);
      final json = goal.toJson();
      expect(json, {
        'id': 4,
        'status': 'paused',
        'is_active': false,
      });
      expect(FitnessGoal.fromJson(json).isActive, isFalse);
    });
  });

  group('ProgressPhoto', () {
    test('parses and round-trips', () {
      final photo = ProgressPhoto.fromJson({
        'id': 6,
        'image_url': 'https://cdn.example.com/progress.png',
        'taken_at': '2026-06-01T08:30:00Z',
        'note': 'front pose',
      });

      expect(photo.id, 6);
      expect(photo.imageUrl, 'https://cdn.example.com/progress.png');
      expect(photo.takenAt, DateTime.parse('2026-06-01T08:30:00Z'));
      expect(photo.note, 'front pose');

      final json = photo.toJson();
      expect(ProgressPhoto.fromJson(json).imageUrl, photo.imageUrl);
    });

    test('toJson omits nulls', () {
      expect(const ProgressPhoto(id: 1).toJson(), {'id': 1});
    });
  });
}