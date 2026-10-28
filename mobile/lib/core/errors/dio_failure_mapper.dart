import 'package:dio/dio.dart';

import 'failures.dart';

/// Maps a [DioException] from a plain FBOS API call to a [Failure].
///
/// Shared by data sources that read non-auth resources (e.g. plan
/// assignments); the auth data source keeps its own bespoke mapping for the
/// login-specific endpoints.
Failure mapDioFailure(DioException e) {
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
        final message =
            (data is Map ? data['detail'] : null) ?? 'Not authorized';
        return AuthFailure(
          message: message.toString(),
          statusCode: statusCode,
        );
      }

      if (statusCode == 400 && data is Map<String, dynamic>) {
        return ValidationFailure(
          message: 'Validation error',
          errors: data,
          statusCode: statusCode,
        );
      }

      final message = (data is Map ? data['detail'] : null) ?? 'Server error';
      return ServerFailure(
        message: message.toString(),
        statusCode: statusCode,
      );

    case DioExceptionType.cancel:
    case DioExceptionType.badCertificate:
    case DioExceptionType.transformTimeout:
    case DioExceptionType.unknown:
      return UnknownFailure(message: e.message ?? 'Unknown error');
  }
}
