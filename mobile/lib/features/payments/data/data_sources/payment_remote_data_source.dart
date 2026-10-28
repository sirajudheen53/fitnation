import 'package:dio/dio.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/dio_failure_mapper.dart';
import '../../../../core/errors/failures.dart';
import '../models/payment_model.dart';

/// Remote data source for the logged-in customer's dues (issue #95).
///
/// Follows the auth data source contract: failures are thrown as [Failure],
/// the repository converts them to result records.
class PaymentRemoteDataSource {
  final Dio _dio;

  PaymentRemoteDataSource(this._dio);

  /// Fetches the customer's own pending payments (the dues they still owe).
  ///
  /// GET /api/v1/payments/?status=pending — the backend self-scopes the
  /// queryset for customer-role tokens. Dues stay readable even when the
  /// app-access entitlement has expired, so this is the one card that
  /// explains a locked-out state. First page only: pending dues are few.
  Future<List<PaymentModel>> fetchPendingPayments() async {
    try {
      final response = await _dio.get(
        AppConstants.paymentsEndpoint,
        queryParameters: {'status': AppConstants.pendingPaymentsStatus},
      );
      final data = response.data as Map<String, dynamic>;
      final results = data['results'] as List<dynamic>;
      return results
          .map((e) => PaymentModel.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw mapDioFailure(e);
    }
  }
}
