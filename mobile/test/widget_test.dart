import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/utils/phone_validator.dart';

void main() {
  group('PhoneValidator', () {
    test('returns error for empty input', () {
      expect(PhoneValidator.validate(''), isNotNull);
      expect(PhoneValidator.validate(null), isNotNull);
      expect(PhoneValidator.validate('  '), isNotNull);
    });

    test('returns error for missing country code', () {
      expect(PhoneValidator.validate('9876543210'), isNotNull);
    });

    test('returns error for non-digit characters', () {
      expect(PhoneValidator.validate('+91abc543210'), isNotNull);
    });

    test('returns error for too short', () {
      expect(PhoneValidator.validate('+919'), isNotNull);
    });

    test('returns null for valid phone', () {
      expect(PhoneValidator.validate('+919876543210'), isNull);
      expect(PhoneValidator.validate('+12025550173'), isNull);
    });

    test('normalizes phone without +', () {
      expect(PhoneValidator.normalize('919876543210'), '+919876543210');
      expect(PhoneValidator.normalize('+919876543210'), '+919876543210');
    });
  });
}