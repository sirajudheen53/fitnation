import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/payments/domain/repositories/payment_repository.dart';

import '../../../../helpers/fakes.dart';
import '../../../../helpers/payment_fakes.dart';

void main() {
  late FakePaymentRemoteDataSource remote;
  late PaymentRepository repository;

  setUp(() {
    remote = FakePaymentRemoteDataSource();
    repository = PaymentRepository(remote);
  });

  test('returns the pending payments on success', () async {
    remote.pendingResult = [pendingPayment()];

    final result = await repository.pendingPayments();

    expect(result.error, isNull);
    expect(result.payments, hasLength(1));
  });

  test('a Failure from the data source becomes the error', () async {
    remote.pendingError = const AuthFailure(message: 'Not authorized');

    final result = await repository.pendingPayments();

    expectFailure(result.error, AuthFailure, messageContains: 'Not authorized');
    expect(result.payments, isNull);
  });

  test('an unexpected error becomes an UnknownFailure', () async {
    remote.pendingError = Exception('boom');

    final result = await repository.pendingPayments();

    expectFailure(result.error, UnknownFailure);
    expect(result.payments, isNull);
  });
}
