import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/utils/currency_formatter.dart';

void main() {
  group('formatRupeeAmount', () {
    test('whole amounts drop the paise and group the rupees', () {
      expect(formatRupeeAmount('1500.00'), '₹1,500');
    });

    test('paise are kept when present', () {
      expect(formatRupeeAmount('1500.50'), '₹1,500.50');
    });

    test('zero stays a bare rupee amount', () {
      expect(formatRupeeAmount('0.00'), '₹0');
    });

    test('amounts without decimals pass through grouped', () {
      expect(formatRupeeAmount('99'), '₹99');
    });

    test('five-digit amounts group once', () {
      expect(formatRupeeAmount('25000.00'), '₹25,000');
    });

    test('six-digit amounts group once', () {
      expect(formatRupeeAmount('150000.00'), '₹150,000');
    });

    test('unparseable input falls back to zero', () {
      expect(formatRupeeAmount('oops'), '₹0');
    });
  });
}
