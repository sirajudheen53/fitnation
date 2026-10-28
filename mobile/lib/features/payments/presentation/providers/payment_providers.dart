import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/data/data_sources/api_client.dart';
import '../../data/data_sources/payment_remote_data_source.dart';
import '../../data/models/payment_model.dart';
import '../../domain/repositories/payment_repository.dart';

/// Load lifecycle of the customer's pending dues.
enum PendingPaymentsStatus { idle, loading, loaded, error }

/// State of the pending dues shown on the home card (issue #95).
@immutable
class PendingPaymentsState {
  final PendingPaymentsStatus status;
  final List<PaymentModel> payments;

  /// Populated when [status] is [PendingPaymentsStatus.error].
  final String? errorMessage;

  const PendingPaymentsState({
    this.status = PendingPaymentsStatus.idle,
    this.payments = const [],
    this.errorMessage,
  });

  PendingPaymentsState copyWith({
    PendingPaymentsStatus? status,
    List<PaymentModel>? payments,
    String? errorMessage,
  }) {
    return PendingPaymentsState(
      status: status ?? this.status,
      payments: payments ?? this.payments,
      errorMessage: errorMessage,
    );
  }
}

/// Loads the customer's pending dues for the home card.
class PendingPaymentsNotifier extends StateNotifier<PendingPaymentsState> {
  final PaymentRepository _repository;

  PendingPaymentsNotifier(this._repository) : super(const PendingPaymentsState());

  /// (Re)loads the pending payments from the backend.
  Future<void> load() async {
    state = state.copyWith(
      status: PendingPaymentsStatus.loading,
      errorMessage: null,
    );

    final result = await _repository.pendingPayments();

    if (result.error != null) {
      state = state.copyWith(
        status: PendingPaymentsStatus.error,
        errorMessage: result.error!.message,
      );
      return;
    }

    state = state.copyWith(
      status: PendingPaymentsStatus.loaded,
      payments: result.payments ?? const [],
    );
  }
}

/// Provides the payment remote data source.
final paymentRemoteDataSourceProvider = Provider<PaymentRemoteDataSource>((ref) {
  return PaymentRemoteDataSource(ApiClient.getInstance());
});

/// Provides the payment repository.
final paymentRepositoryProvider = Provider<PaymentRepository>((ref) {
  return PaymentRepository(ref.read(paymentRemoteDataSourceProvider));
});

/// Provides the customer's pending dues for the home card.
final pendingPaymentsProvider =
    StateNotifierProvider<PendingPaymentsNotifier, PendingPaymentsState>((ref) {
  return PendingPaymentsNotifier(ref.read(paymentRepositoryProvider));
});
