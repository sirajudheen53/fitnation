import '../../../../core/errors/failures.dart';
import '../../data/data_sources/payment_remote_data_source.dart';
import '../../data/models/payment_model.dart';

/// Repository for the logged-in customer's pending dues (issue #95).
class PaymentRepository {
  final PaymentRemoteDataSource _remote;

  PaymentRepository(this._remote);

  /// The customer's pending payments.
  Future<({List<PaymentModel>? payments, Failure? error})>
      pendingPayments() async {
    try {
      final payments = await _remote.fetchPendingPayments();
      return (payments: payments, error: null);
    } on Failure catch (e) {
      return (payments: null, error: e);
    } catch (e) {
      return (payments: null, error: UnknownFailure(message: e.toString()));
    }
  }
}
