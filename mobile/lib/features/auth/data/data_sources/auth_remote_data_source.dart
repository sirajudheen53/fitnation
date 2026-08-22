import 'package:dio/dio.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/failures.dart';
import '../models/auth_response.dart';

/// Remote data source for authentication (OTP flow).
class AuthRemoteDataSource {
  final Dio _dio;

  AuthRemoteDataSource(this._dio);

  /// Requests an OTP to be sent to [phone].
  ///
  /// POST /api/v1/auth/otp/request/
  /// Body: { "phone": "+919876543210" }
  Future<void> requestOtp(String phone) async {
    try {
      await _dio.post(
        AppConstants.otpRequestEndpoint,
        data: {'phone': phone},
      );
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Verifies the OTP and returns the auth response (token + user + permissions).
  ///
  /// POST /api/v1/auth/otp/verify/
  /// Body: { "phone": "+919876543210", "otp": "123456", "device_type": "android" }
  Future<AuthResponse> verifyOtp({
    required String phone,
    required String otp,
    required String deviceType,
    String? deviceId,
    String? userAgent,
  }) async {
    try {
      final response = await _dio.post(
        AppConstants.otpVerifyEndpoint,
        data: {
          'phone': phone,
          'otp': otp,
          'device_type': deviceType,
          if (deviceId != null) 'device_id': deviceId,
          if (userAgent != null) 'user_agent': userAgent,
        },
      );
      return AuthResponse.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Logs out the current user (deactivates token).
  Future<void> logout() async {
    try {
      await _dio.post(AppConstants.logoutEndpoint);
    } on DioException catch (e) {
      // If token is already invalid, logout is effectively done.
      if (e.response?.statusCode != 401) {
        throw _mapDioError(e);
      }
    }
  }

  /// Fetches the current user's profile.
  Future<AuthResponse> getCurrentUser() async {
    try {
      final response = await _dio.get(AppConstants.meEndpoint);
      return AuthResponse.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
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
      case DioExceptionType.unknown:
        return UnknownFailure(message: e.message ?? 'Unknown error');
    }
  }
}