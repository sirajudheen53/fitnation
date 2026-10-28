import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/payments/data/data_sources/payment_remote_data_source.dart';
import 'package:fitnation_app/features/payments/data/models/payment_model.dart';
import 'package:fitnation_app/features/payments/domain/repositories/payment_repository.dart';

/// Canned pending-payment row shared across payment tests.
PaymentModel pendingPayment({int id = 10, String amount = '1500.00'}) =>
    PaymentModel(
      id: id,
      kind: 'membership',
      amount: amount,
      status: 'pending',
      planName: 'Monthly',
      paymentDate: DateTime(2026, 10, 28, 10, 0),
    );

/// Recording fake for [PaymentRemoteDataSource].
class FakePaymentRemoteDataSource implements PaymentRemoteDataSource {
  List<PaymentModel> pendingResult = const [];
  Object? pendingError;
  int pendingCalls = 0;

  @override
  Future<List<PaymentModel>> fetchPendingPayments() async {
    pendingCalls++;
    final error = pendingError;
    if (error != null) throw error;
    return pendingResult;
  }
}

/// Repository fake backed by [FakePaymentRemoteDataSource], mirroring the
/// real repository's Failure-to-record conversion.
class FakePaymentRepository implements PaymentRepository {
  FakePaymentRepository(this._remote);

  final FakePaymentRemoteDataSource _remote;

  @override
  Future<({List<PaymentModel>? payments, Failure? error})>
      pendingPayments() async {
    try {
      final payments = await _remote.fetchPendingPayments();
      return (payments: payments, error: null);
    } on Failure catch (e) {
      return (payments: null, error: e);
    }
  }
}
