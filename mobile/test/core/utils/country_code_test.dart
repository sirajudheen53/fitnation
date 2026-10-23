import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/utils/country_code.dart';

void main() {
  group('CountryCodes registry', () {
    test('default is India +91 with the strict 10-digit rule', () {
      expect(CountryCodes.defaultCode.code, 'IN');
      expect(CountryCodes.defaultCode.dialCode, '91');
      expect(CountryCodes.defaultCode.minLength, 10);
      expect(CountryCodes.defaultCode.maxLength, 10);
      // India must stay the first entry — it is the picker's initial row.
      expect(CountryCodes.all.first.code, 'IN');
    });

    test('is a compact but sensible list', () {
      expect(CountryCodes.all.length, inInclusiveRange(25, 40));
      // The diaspora corridors the gyms actually see.
      for (final dial in ['1', '44', '61', '65', '971', '966']) {
        expect(
          CountryCodes.all.any((c) => c.dialCode == dial),
          isTrue,
          reason: 'expected a country with dial code +$dial',
        );
      }
    });

    test('entries are well-formed and unique by ISO code', () {
      final seen = <String>{};
      for (final c in CountryCodes.all) {
        expect(c.code, matches(RegExp(r'^[A-Z]{2}$')), reason: c.code);
        expect(c.name, isNotEmpty);
        expect(c.dialCode, matches(RegExp(r'^\d{1,4}$')), reason: c.code);
        expect(c.minLength, inInclusiveRange(4, 13), reason: c.code);
        expect(c.maxLength, lessThanOrEqualTo(14), reason: c.code);
        expect(c.minLength, lessThanOrEqualTo(c.maxLength), reason: c.code);
        expect(seen.add(c.code), isTrue, reason: 'duplicate ISO ${c.code}');
      }
    });

    test('flags are real flag emoji derived from the ISO code', () {
      expect(CountryCodes.defaultCode.flag, '🇮🇳');
      expect(CountryCodes.findByIso('AE')!.flag, '🇦🇪');
      expect(CountryCodes.findByIso('GB')!.flag, '🇬🇧');
    });

    test('findByIso is case-insensitive and null-safe', () {
      expect(CountryCodes.findByIso('in')?.code, 'IN');
      expect(CountryCodes.findByIso('AE')?.code, 'AE');
      expect(CountryCodes.findByIso(null), isNull);
      expect(CountryCodes.findByIso(''), isNull);
      expect(CountryCodes.findByIso('XX'), isNull);
    });

    test('numberHint renders exact and ranged plans', () {
      expect(CountryCodes.defaultCode.numberHint, '10-digit number');
      expect(CountryCodes.findByIso('AE')!.numberHint, '7–9 digit number');
    });
  });
}
