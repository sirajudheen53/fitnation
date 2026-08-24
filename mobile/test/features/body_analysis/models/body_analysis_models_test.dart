import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/body_analysis/models/body_analysis.dart';
import 'package:fitnation_app/features/body_analysis/models/body_photo.dart';
import 'package:fitnation_app/features/body_analysis/models/progress_log.dart';

void main() {
  group('BodyAnalysis', () {
    test('fromJson parses metrics', () {
      final json = {
        'id': 1,
        'bmi': 24.5,
        'body_fat_percentage': 18.2,
        'posture_score': 85,
        'weight': 70.5,
        'status': 'good',
      };

      final analysis = BodyAnalysis.fromJson(json);

      expect(analysis.id, 1);
      expect(analysis.bmi, 24.5);
      expect(analysis.bodyFatPercentage, 18.2);
      expect(analysis.postureScore, 85);
      expect(analysis.status, 'good');
    });
  });

  group('BodyPhoto', () {
    test('fromJson parses photo type', () {
      final json = {
        'id': 1,
        'url': 'http://example.com/photo.jpg',
        'photo_type': 'side',
      };

      final photo = BodyPhoto.fromJson(json);

      expect(photo.id, 1);
      expect(photo.photoType, 'side');
      expect(photo.url, 'http://example.com/photo.jpg');
    });

    test('has front, side and back types', () {
      expect(BodyPhoto.types, containsAll(['front', 'side', 'back']));
    });
  });

  group('ProgressLog', () {
    test('fromJson parses weight', () {
      final log = ProgressLog.fromJson({
        'id': 1,
        'weight': 72.3,
        'body_fat_percentage': 18.0,
      });

      expect(log.id, 1);
      expect(log.weight, 72.3);
      expect(log.bodyFatPercentage, 18.0);
    });
  });
}
