import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../../../../core/constants/app_constants.dart';

/// Singleton Dio instance configured for the FBOS API.
class ApiClient {
  ApiClient._();

  static Dio? _instance;

  /// Hook the app sets at startup: invoked whenever the server answers 403
  /// with an `app_access_*` code (FBOS-011 §2.4). The handler flips the local
  /// entitlement state so the router gates the member on the next frame —
  /// mid-session revocation needs no extra round-trip.
  static void Function(String code)? onAccessDenied;

  /// Gets the configured Dio instance.
  /// If [token] is provided, it will be set as the Authorization header.
  static Dio getInstance({String? token}) {
    if (_instance == null) {
      _instance = Dio(BaseOptions(
        baseUrl: '${AppConstants.apiBaseUrl}${AppConstants.apiPrefix}',
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 30),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ));

      _instance!.interceptors.add(_AccessDeniedInterceptor());

      if (kDebugMode) {
        _instance!.interceptors.add(LogInterceptor(
          request: true,
          requestHeader: true,
          requestBody: true,
          responseHeader: false,
          responseBody: true,
          error: true,
        ));
      }
    }

    // Update auth header
    if (token != null) {
      _instance!.options.headers['Authorization'] = 'Token $token';
    } else {
      _instance!.options.headers.remove('Authorization');
    }

    return _instance!;
  }

  /// Recreates the Dio instance (e.g. on logout or token change).
  static void reset() {
    _instance = null;
  }
}

/// Surfaces entitlement 403s (`app_access_required` /
/// `app_access_read_only`) to [ApiClient.onAccessDenied].
class _AccessDeniedInterceptor extends Interceptor {
  static const Set<String> _accessCodes = {
    'app_access_required',
    'app_access_read_only',
  };

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    final data = err.response?.data;
    final code = data is Map ? data['code'] as String? : null;
    if (err.response?.statusCode == 403 &&
        code != null &&
        _accessCodes.contains(code) &&
        ApiClient.onAccessDenied != null) {
      ApiClient.onAccessDenied!(code);
    }
    handler.next(err);
  }
}
