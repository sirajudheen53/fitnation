import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/payments/data/models/payment_model.dart';

void main() {
  Map<String, dynamic> row({int id = 10, String amount = '1500.00'}) => {
        'id': id,
        'customer_id': 5,
        'customer_name': 'Arjun Nair',
        'customer_is_deleted': false,
        'customer_phone': '+919876543210',
        'membership_id': 3,
        'plan_name': 'Monthly',
        'invoice_id': null,
        'kind': 'membership',
        'amount': amount,
        'method': 'upi',
        'status': 'pending',
        'transaction_id': '',
        'razorpay_order_id': '',
        'razorpay_payment_id': '',
        'payment_date': '2026-10-28T10:00:00+05:30',
        'notes': '',
        'created_at': '2026-10-28T05:30:00Z',
        'updated_at': '2026-10-28T05:30:00Z',
      };

  group('PaymentModel', () {
    test('parses a pending membership payment', () {
      final payment = PaymentModel.fromJson(row());

      expect(payment.id, 10);
      expect(payment.kind, 'membership');
      expect(payment.amount, '1500.00');
      expect(payment.status, 'pending');
      expect(payment.isPending, isTrue);
      expect(payment.planName, 'Monthly');
      expect(payment.paymentDate, DateTime.utc(2026, 10, 28, 4, 30));
      expect(payment.notes, '');
    });

    test('falls back to created_at when payment_date is missing', () {
      final json = row()..remove('payment_date');

      expect(
        PaymentModel.fromJson(json).paymentDate,
        DateTime.utc(2026, 10, 28, 5, 30),
      );
    });

    test('equality is by id', () {
      final a = PaymentModel.fromJson(row());
      expect(a, PaymentModel.fromJson(row()));
      expect(a, isNot(PaymentModel.fromJson(row(id: 11))));
    });
  });

  group('PaymentModel.totalAmount', () {
    test('sums the decimal amounts', () {
      final payments = [
        PaymentModel.fromJson(row(id: 1, amount: '1500.00')),
        PaymentModel.fromJson(row(id: 2, amount: '250.50')),
      ];

      expect(PaymentModel.totalAmount(payments), 1750.5);
    });

    test('empty list sums to zero', () {
      expect(PaymentModel.totalAmount(const []), 0);
    });

    test('unparseable amounts count as zero', () {
      final payments = [PaymentModel.fromJson(row(amount: 'oops'))];

      expect(PaymentModel.totalAmount(payments), 0);
    });
  });
}
