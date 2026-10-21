import 'package:dio/dio.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/failures.dart';
import '../models/auth_response.dart';
import '../models/entitlement.dart';

/// Remote data source for authentication (OTP flow).
class AuthRemoteDataSource {
  final Dio _dio;

  AuthRemoteDataSource(this._dio);

  /// Requests an OTP to be sent to [phone].
  ///
  /// POST /api/v1/users/auth/otp/request/
  /// Body: `{ "phone": "+919876543210", "gym": "<tenant-uuid>"? }`
  ///
  /// [gymAnchor] is the effective gym anchor (runtime link anchor wins over
  /// the build-time dart-define — see `AnchorStore` docs).
  Future<void> requestOtp(String phone, {String? gymAnchor}) async {
    try {
      await _dio.post(
        AppConstants.otpRequestEndpoint,
        data: {
          'phone': phone,
          if (gymAnchor != null && gymAnchor.isNotEmpty) 'gym': gymAnchor,
        },
      );
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Verifies the OTP and returns the auth response.
  ///
  /// POST /api/v1/users/auth/otp/verify/
  /// Body: { "phone", "otp", "gym"?, "device_type", "device_id"?, "user_agent"? }
  ///
  /// The anchor is sent on verify too (FBOS-011 correction #6) so a member of
  /// two gyms is pinned to the gym whose link they installed from.
  Future<AuthResponse> verifyOtp({
    required String phone,
    required String otp,
    required String deviceType,
    String? deviceId,
    String? userAgent,
    String? gymAnchor,
  }) async {
    try {
      final response = await _dio.post(
        AppConstants.otpVerifyEndpoint,
        data: {
          'phone': phone,
          'otp': otp,
          'device_type': deviceType,
          'device_id': ?deviceId,
          'user_agent': ?userAgent,
          if (gymAnchor != null && gymAnchor.isNotEmpty) 'gym': gymAnchor,
        },
      );
      return AuthResponse.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Live app-access entitlement (FBOS-011 §2.3c).
  ///
  /// GET /api/v1/users/auth/entitlement/ — called on app resume and after a
  /// 403 `app_access_*` to re-derive the gate state from the server.
  Future<Entitlement> fetchEntitlement() async {
    try {
      final response = await _dio.get(AppConstants.entitlementEndpoint);
      return Entitlement.fromJson(response.data as Map<String, dynamic>);
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
          final detail = (data['detail'] ?? data['gym'] ?? data.values.firstOrNull?.firstOrNull ?? 'Validation error').toString();
          return ValidationFailure(
            message: detail,
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
