import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../../core/constants/app_constants.dart';

/// Singleton Dio instance configured for the FBOS API.
class ApiClient {
  ApiClient._();

  static Dio? _instance;

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