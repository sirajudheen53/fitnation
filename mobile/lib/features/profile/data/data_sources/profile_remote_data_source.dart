import 'package:dio/dio.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/failures.dart';
import '../models/customer_profile.dart';

/// Remote data source for profile-related endpoints.
class ProfileRemoteDataSource {
  final Dio _dio;

  ProfileRemoteDataSource(this._dio);

  /// Fetches the customer profile.
  ///
  /// GET /api/v1/customers/customers/{id}/
  Future<CustomerProfile> getProfile(int customerId) async {
    try {
      final response = await _dio.get(
        '${AppConstants.customerProfileEndpoint}$customerId/',
      );
      return CustomerProfile.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Updates the customer profile.
  ///
  /// PATCH /api/v1/customers/customers/{id}/
  Future<CustomerProfile> updateProfile(
    int customerId,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _dio.patch(
        '${AppConstants.customerProfileEndpoint}$customerId/',
        data: data,
      );
      return CustomerProfile.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Updates the health profile for a customer.
  ///
  /// PATCH /api/v1/customers/customers/{id}/health-profile/
  Future<HealthProfile> updateHealthProfile(
    int customerId,
    Map<String, dynamic> data,
  ) async {
    try {
      final response = await _dio.patch(
        AppConstants.customerHealthProfileEndpoint.replaceAll('{id}', '$customerId'),
        data: data,
      );
      return HealthProfile.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Fetches the health profile for a customer.
  ///
  /// GET /api/v1/customers/customers/{id}/health-profile/
  Future<HealthProfile?> getHealthProfile(int customerId) async {
    try {
      final response = await _dio.get(
        AppConstants.customerHealthProfileEndpoint.replaceAll('{id}', '$customerId'),
      );
      return HealthProfile.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      // 404 means no health profile yet.
      if (e.response?.statusCode == 404) return null;
      throw _mapDioError(e);
    }
  }

  /// Fetches the membership info for a customer.
  ///
  /// GET /api/v1/memberships/memberships/?customer={id}
  Future<List<Membership>> getMemberships(int customerId) async {
    try {
      final response = await _dio.get(
        AppConstants.membershipsEndpoint,
        queryParameters: {'customer': customerId},
      );
      final results = _extractResults(response.data);
      return results
          .map((e) => Membership.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Extracts a list of results from a paginated or plain list response.
  List<dynamic> _extractResults(dynamic data) {
    if (data is List) return data;
    if (data is Map && data['results'] is List) {
      return data['results'] as List;
    }
    return const [];
  }

  /// Maps a DioException to a Failure.
  Failure _mapDioError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.connectionError:
        return const NetworkFailure();
      case DioExceptionType.badResponse:
        final statusCode = e.response?.statusCode;
        final data = e.response?.data;
        if (statusCode == 401 || statusCode == 403) {
          final message = (data is Map ? data['detail'] : null) ?? 'Authentication failed';
          return AuthFailure(message: message.toString(), statusCode: statusCode);
        }
        if (statusCode == 400 && data is Map<String, dynamic>) {
          return ValidationFailure(
            message: 'Validation error',
            errors: data,
            statusCode: statusCode,
          );
        }
        final message = (data is Map ? data['detail'] : null) ?? 'Server error';
        return ServerFailure(message: message.toString(), statusCode: statusCode);
      case DioExceptionType.cancel:
      case DioExceptionType.badCertificate:
      case DioExceptionType.transformTimeout:
      case DioExceptionType.unknown:
        return UnknownFailure(message: e.message ?? 'Unknown error');
    }
  }
}
