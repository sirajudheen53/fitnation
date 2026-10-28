import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/utils/date_formatter.dart';

void main() {
  group('formatDateShort', () {
    test('formats a date as zero-padded day, abbreviated month, year', () {
      expect(formatDateShort(DateTime(2026, 10, 1)), '01 Oct 2026');
      expect(formatDateShort(DateTime(2026, 10, 28)), '28 Oct 2026');
    });

    test('covers every month abbreviation', () {
      const expected = [
        'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
      ];
      for (var i = 0; i < expected.length; i++) {
        expect(
          formatDateShort(DateTime(2026, i + 1, 15)),
          '15 ${expected[i]} 2026',
        );
      }
    });

    test('pads single-digit days', () {
      expect(formatDateShort(DateTime(2026, 3, 5)), '05 Mar 2026');
      expect(formatDateShort(DateTime(2026, 12, 31)), '31 Dec 2026');
    });
  });

  group('formatTimeShort', () {
    test('formats morning times with AM', () {
      expect(formatTimeShort(DateTime(2026, 10, 28, 9, 5)), '9:05 AM');
      expect(formatTimeShort(DateTime(2026, 10, 28, 0, 7)), '12:07 AM');
    });

    test('formats afternoon and evening times with PM', () {
      expect(formatTimeShort(DateTime(2026, 10, 28, 18, 4)), '6:04 PM');
      expect(formatTimeShort(DateTime(2026, 10, 28, 12, 0)), '12:00 PM');
      expect(formatTimeShort(DateTime(2026, 10, 28, 23, 59)), '11:59 PM');
    });

    test('pads single-digit minutes', () {
      expect(formatTimeShort(DateTime(2026, 10, 28, 15, 4)), '3:04 PM');
    });
  });
}
