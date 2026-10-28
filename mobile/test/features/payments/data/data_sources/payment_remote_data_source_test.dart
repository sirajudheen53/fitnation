import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/payments/data/data_sources/payment_remote_data_source.dart';

import '../../../../helpers/fakes.dart';

void main() {
  Map<String, dynamic> paymentRow({int id = 10, String amount = '1500.00'}) => {
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

  test('fetchPendingPayments GETs payments filtered to pending', () async {
    final requests = <RequestOptions>[];
    final adapter = FakeDioAdapter((options) {
      requests.add(options);
      return FakeDioAdapter.json({
        'count': 1,
        'next': null,
        'previous': null,
        'results': [paymentRow()],
      });
    });
    final source = PaymentRemoteDataSource(FakeDioAdapter.client(adapter));

    final payments = await source.fetchPendingPayments();

    expect(payments, hasLength(1));
    expect(payments.first.amount, '1500.00');
    expect(payments.first.isPending, isTrue);
    expect(requests.single.method, 'GET');
    expect(requests.single.path, '/payments/');
    expect(requests.single.queryParameters['status'], 'pending');
  });

  test('a 403 surfaces as an AuthFailure', () async {
    final adapter = FakeDioAdapter(
        (options) => FakeDioAdapter.json({'detail': 'Nope'}, 403));
    final source = PaymentRemoteDataSource(FakeDioAdapter.client(adapter));

    await expectLater(
      source.fetchPendingPayments(),
      throwsA(isA<AuthFailure>()),
    );
  });
}
