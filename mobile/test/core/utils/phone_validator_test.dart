import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/utils/country_code.dart';
import 'package:fitnation_app/core/utils/phone_validator.dart';

void main() {
  final india = CountryCodes.defaultCode; // +91, 10 digits
  final uae = CountryCodes.findByIso('AE')!; // +971, 7–9 digits
  final us = CountryCodes.findByIso('US')!; // +1, 10 digits

  group('PhoneValidator.validateNational', () {
    test('empty input asks for a phone number regardless of dial code', () {
      expect(PhoneValidator.validateNational(null, india), isNotNull);
      expect(PhoneValidator.validateNational('', india), isNotNull);
      expect(PhoneValidator.validateNational('   ', india), isNotNull);
    });

    test('India keeps the strict 10-digit rule', () {
      expect(PhoneValidator.validateNational('9876543210', india), isNull);
      expect(PhoneValidator.validateNational('987654321', india), isNotNull);
      expect(PhoneValidator.validateNational('98765432100', india), isNotNull);
    });

    test('validation swaps with the dial code', () {
      // 8 digits: too short for India, inside the UAE 7–9 range.
      expect(PhoneValidator.validateNational('50123456', india), isNotNull);
      expect(PhoneValidator.validateNational('50123456', uae), isNull);
      // 10 digits: right for India, too long for the UAE.
      expect(PhoneValidator.validateNational('5012345678', india), isNull);
      expect(PhoneValidator.validateNational('5012345678', uae), isNotNull);
    });

    test('US numbers are 10 national digits under +1', () {
      expect(PhoneValidator.validateNational('2025550173', us), isNull);
      expect(PhoneValidator.validateNational('202555017', us), isNotNull);
    });

    test('letters are rejected', () {
      expect(PhoneValidator.validateNational('98abcd43210', india), isNotNull);
    });

    test('formatting characters are tolerated', () {
      expect(PhoneValidator.validateNational('98765 43210', india), isNull);
      expect(PhoneValidator.validateNational('98765-43210', india), isNull);
    });
  });

  group('PhoneValidator.toNationalDigits', () {
    test('strips formatting characters', () {
      expect(PhoneValidator.toNationalDigits('98765 43210', india),
          '9876543210');
    });

    test('strips a leading trunk zero', () {
      expect(PhoneValidator.toNationalDigits('09876543210', india),
          '9876543210');
    });

    test('strips a pasted dial-code prefix only when unambiguous', () {
      // "+91 98765 43210" pasted with India selected → no double country
      // code; the full 12 digits cannot be a national number, the
      // remainder can.
      expect(PhoneValidator.toNationalDigits('+919876543210', india),
          '9876543210');
      // Same for the +1 convention: 11 digits starting with 1.
      expect(PhoneValidator.toNationalDigits('12025550173', us), '2025550173');
    });

    test('keeps a genuine number that merely starts with the dial code', () {
      // 9198765432 is 10 digits — a valid Indian number, not a pasted +91.
      expect(PhoneValidator.toNationalDigits('9198765432', india),
          '9198765432');
    });

    test('no strip when the remainder would be invalid', () {
      // 13 digits; stripping "91" leaves 11 — still too long for India,
      // so the input is kept as-is (and validation rejects it).
      expect(PhoneValidator.toNationalDigits('9198765432109', india),
          '9198765432109');
    });
  });

  group('PhoneValidator.normalize', () {
    test('builds +<dial><national> with the country code exactly once', () {
      expect(PhoneValidator.normalize('9876543210', india), '+919876543210');
      expect(PhoneValidator.normalize('501234567', uae), '+971501234567');
      expect(PhoneValidator.normalize('2025550173', us), '+12025550173');
    });

    test('pasted international input normalizes without doubling', () {
      expect(PhoneValidator.normalize('+919876543210', india),
          '+919876543210');
      expect(PhoneValidator.normalize('+91 98765 43210', india),
          '+919876543210');
      expect(PhoneValidator.normalize('+12025550173', us), '+12025550173');
    });
  });
}
