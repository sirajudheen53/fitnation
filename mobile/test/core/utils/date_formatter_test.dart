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
}
