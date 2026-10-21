import 'package:dio/dio.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/failures.dart';

/// A registered push device (mirrors the backend `DeviceToken`).
class DeviceRegistration {
  const DeviceRegistration({
    required this.id,
    required this.token,
    required this.platform,
  });

  final int id;
  final String token;
  final String platform;
}

/// Remote data source for FCM device-token registration
/// (`POST/DELETE /api/v1/notifications/device-tokens/`, FBOS-011 §7.4 / B7).
class DeviceRemoteDataSource {
  final Dio _dio;

  DeviceRemoteDataSource(this._dio);

  /// Registers (upserts) the FCM token. Idempotent per token — the backend
  /// answers 201 on first registration, 200 on re-registration.
  Future<void> register({
    required String token,
    required String deviceId,
    required String platform,
    String deviceType = 'android',
  }) async {
    try {
      await _dio.post(
        AppConstants.deviceTokensEndpoint,
        data: {
          'token': token,
          'device_id': deviceId,
          'platform': platform,
          'device_type': deviceType,
        },
      );
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Deletes this device's registration (logout path).
  ///
  /// The endpoint is a ModelViewSet (delete by id), so the caller's own rows
  /// are listed first and the matching token removed. A 404 anywhere means
  /// it's already gone — success for our purposes.
  Future<void> unregister(String token) async {
    try {
      final response = await _dio.get(AppConstants.deviceTokensEndpoint);
      final data = response.data;
      final items = data is Map<String, dynamic>
          ? (data['results'] as List<dynamic>? ?? const [])
          : (data is List ? data : const []);
      for (final item in items) {
        if (item is Map<String, dynamic> && item['token'] == token) {
          final id = item['id'];
          await _dio.delete('${AppConstants.deviceTokensEndpoint}$id/');
          return;
        }
      }
      // Not listed — nothing to delete.
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return;
      throw _mapDioError(e);
    }
  }

  Failure _mapDioError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.connectionError:
        return const NetworkFailure();
      case DioExceptionType.badResponse:
        final data = e.response?.data;
        final message = (data is Map ? data['detail'] : null)?.toString() ??
            'Device registration failed';
        return ServerFailure(
          message: message,
          statusCode: e.response?.statusCode,
        );
      case DioExceptionType.cancel:
      case DioExceptionType.badCertificate:
      case DioExceptionType.transformTimeout:
      case DioExceptionType.unknown:
        return UnknownFailure(message: e.message ?? 'Unknown error');
    }
  }
}
