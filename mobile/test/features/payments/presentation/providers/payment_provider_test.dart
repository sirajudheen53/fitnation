import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/payments/presentation/providers/payment_providers.dart';

import '../../../../helpers/payment_fakes.dart';

void main() {
  late FakePaymentRemoteDataSource remote;
  late ProviderContainer container;

  setUp(() {
    remote = FakePaymentRemoteDataSource();
    container = ProviderContainer(
      overrides: [
        paymentRepositoryProvider
            .overrideWithValue(FakePaymentRepository(remote)),
      ],
    );
  });

  tearDown(() => container.dispose());

  PendingPaymentsState state() => container.read(pendingPaymentsProvider);

  test('starts idle before any load', () {
    expect(state().status, PendingPaymentsStatus.idle);
    expect(state().payments, isEmpty);
  });

  test('load transitions idle → loaded with the payments', () async {
    remote.pendingResult = [pendingPayment(), pendingPayment(id: 11)];

    await container.read(pendingPaymentsProvider.notifier).load();

    expect(state().status, PendingPaymentsStatus.loaded);
    expect(state().payments, hasLength(2));
    expect(state().errorMessage, isNull);
  });

  test('no dues still lands in loaded with an empty list', () async {
    await container.read(pendingPaymentsProvider.notifier).load();

    expect(state().status, PendingPaymentsStatus.loaded);
    expect(state().payments, isEmpty);
  });

  test('load surfaces the failure message on error', () async {
    remote.pendingError = const AuthFailure(message: 'Not authorized');

    await container.read(pendingPaymentsProvider.notifier).load();

    expect(state().status, PendingPaymentsStatus.error);
    expect(state().errorMessage, 'Not authorized');
    expect(state().payments, isEmpty);
  });

  test('a successful refresh replaces the payments', () async {
    remote.pendingResult = [pendingPayment()];
    await container.read(pendingPaymentsProvider.notifier).load();

    remote.pendingResult = const [];
    await container.read(pendingPaymentsProvider.notifier).load();

    expect(state().status, PendingPaymentsStatus.loaded);
    expect(state().payments, isEmpty);
  });
}
