import 'package:dio/dio.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/failures.dart';
import '../models/diet_plan.dart';

/// Remote data source for diet-related endpoints.
class DietRemoteDataSource {
  final Dio _dio;

  DietRemoteDataSource(this._dio);

  /// Fetches the active diet assignment for a customer.
  ///
  /// GET /api/v1/diet/diet-assignments/?customer={id}&is_active=true
  Future<DietAssignment?> getActiveAssignment(int customerId) async {
    try {
      final response = await _dio.get(
        AppConstants.dietAssignmentsEndpoint,
        queryParameters: {'customer': customerId, 'is_active': true},
      );
      final results = _extractResults(response.data);
      if (results.isEmpty) return null;
      return DietAssignment.fromJson(results.first);
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Fetches a diet plan by id (with days, meals, and food items).
  ///
  /// GET /api/v1/diet/diet-plans/{id}/
  Future<DietPlan> getDietPlan(int planId) async {
    try {
      final response = await _dio.get(
        '${AppConstants.dietPlansEndpoint}$planId/',
      );
      return DietPlan.fromJson(response.data as Map<String, dynamic>);
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
