import 'package:dio/dio.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/failures.dart';
import '../models/attendance_record.dart';

/// Remote data source for attendance-related endpoints.
class AttendanceRemoteDataSource {
  final Dio _dio;

  AttendanceRemoteDataSource(this._dio);

  /// Fetches the attendance history for a customer.
  ///
  /// GET /api/v1/attendance/attendance-records/?customer={id}
  Future<List<AttendanceRecord>> getAttendanceHistory(int customerId) async {
    try {
      final response = await _dio.get(
        AppConstants.attendanceRecordsEndpoint,
        queryParameters: {'customer': customerId},
      );
      final results = _extractResults(response.data);
      return results
          .map((e) => AttendanceRecord.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Performs a QR check-in.
  ///
  /// POST /api/v1/attendance/attendance-records/check-in/
  /// Body: { "qr_code": "...", "customer": id }
  Future<AttendanceRecord> checkIn({
    required String qrCode,
    int? customerId,
  }) async {
    try {
      final response = await _dio.post(
        AppConstants.attendanceCheckInEndpoint,
        data: {
          'qr_code': qrCode,
          'customer': ?customerId,
        },
      );
      return AttendanceRecord.fromJson(response.data as Map<String, dynamic>);
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
