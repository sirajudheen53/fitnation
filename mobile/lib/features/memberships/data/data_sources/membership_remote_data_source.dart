import 'package:dio/dio.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/dio_failure_mapper.dart';
import '../../../../core/errors/failures.dart';
import '../models/membership_model.dart';

/// Remote data source for the logged-in customer's memberships (issue #95).
///
/// Follows the auth data source contract: failures are thrown as [Failure],
/// the repository converts them to result records.
class MembershipRemoteDataSource {
  final Dio _dio;

  MembershipRemoteDataSource(this._dio);

  /// Fetches the customer's own memberships.
  ///
  /// GET /api/v1/memberships/memberships/ — the backend self-scopes the
  /// queryset for customer-role tokens. First page is enough: the home card
  /// shows the current membership, and memberships are few per customer.
  Future<List<MembershipModel>> fetchMyMemberships() async {
    try {
      final response = await _dio.get(AppConstants.membershipsEndpoint);
      final data = response.data as Map<String, dynamic>;
      final results = data['results'] as List<dynamic>;
      return results
          .map((e) => MembershipModel.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw mapDioFailure(e);
    }
  }
}
