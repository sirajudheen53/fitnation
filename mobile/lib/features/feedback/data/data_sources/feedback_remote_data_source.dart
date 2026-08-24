import 'package:dio/dio.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/failures.dart';
import '../models/feedback.dart';

/// Remote data source for feedback endpoints.
class FeedbackRemoteDataSource {
  final Dio _dio;

  FeedbackRemoteDataSource(this._dio);

  /// Submits feedback.
  ///
  /// POST /api/v1/feedback/feedback/
  Future<Feedback> submitFeedback(Feedback feedback) async {
    try {
      final response = await _dio.post(
        AppConstants.feedbackEndpoint,
        data: feedback.toJson(),
      );
      return Feedback.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Fetches the feedback submitted by a customer.
  ///
  /// GET /api/v1/feedback/feedback/?customer={id}
  Future<List<Feedback>> getFeedback(int customerId) async {
    try {
      final response = await _dio.get(
        AppConstants.feedbackEndpoint,
        queryParameters: {'customer': customerId},
      );
      final results = _extractResults(response.data);
      return results
          .map((e) => Feedback.fromJson(e as Map<String, dynamic>))
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
