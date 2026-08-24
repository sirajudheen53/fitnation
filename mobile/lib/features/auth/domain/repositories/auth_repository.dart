import 'dart:io';

import 'package:device_info_plus/device_info_plus.dart';

import '../../../../core/errors/failures.dart';
import '../../data/data_sources/api_client.dart';
import '../../data/data_sources/auth_local_data_source.dart';
import '../../data/data_sources/auth_remote_data_source.dart';
import '../../data/models/auth_response.dart';
import '../../data/models/user_model.dart';

/// Repository that coordinates local and remote auth data sources.
class AuthRepository {
  final AuthRemoteDataSource _remote;
  final AuthLocalDataSource _local;

  AuthRepository(this._remote, this._local);

  /// Requests an OTP for the given phone number.
  Future<({Failure? error})> requestOtp(String phone) async {
    try {
      await _remote.requestOtp(phone);
      return (error: null);
    } on Failure catch (e) {
      return (error: e);
    } catch (e) {
      return (error: UnknownFailure(message: e.toString()));
    }
  }

  /// Verifies the OTP and stores the auth session.
  Future<({AuthResponse? response, Failure? error})> verifyOtp({
    required String phone,
    required String otp,
  }) async {
    try {
      final deviceInfo = await _getDeviceInfo();
      final response = await _remote.verifyOtp(
        phone: phone,
        otp: otp,
        deviceType: deviceInfo.type,
        deviceId: deviceInfo.id,
        userAgent: deviceInfo.userAgent,
      );

      // Persist auth state
      final token = response.token;
      if (token == null) {
        return (response: null, error: const AuthFailure(message: 'No token returned'));
      }
      await _local.saveToken(token);
      await _local.saveUser(response.user);
      await _local.savePermissions(response.permissions);

      // Update API client with new token
      ApiClient.getInstance(token: token);

      return (response: response, error: null);
    } on Failure catch (e) {
      return (response: null, error: e);
    } catch (e) {
      return (response: null, error: UnknownFailure(message: e.toString()));
    }
  }

  /// Restores the auth session from local storage (auto-login).
  ({UserModel? user, List<String> permissions, String? token}) restoreSession() {
    final token = _local.getToken();
    final user = _local.getUser();
    final permissions = _local.getPermissions();

    if (token != null && user != null) {
      ApiClient.getInstance(token: token);
    }

    return (user: user, permissions: permissions, token: token);
  }

  /// Logs out the user and clears local data.
  Future<void> logout() async {
    try {
      await _remote.logout();
    } finally {
      await _local.clear();
      ApiClient.reset();
    }
  }

  /// Gets the current user profile from the server (refresh).
  Future<({UserModel? user, List<String>? permissions, Failure? error})>
      refreshProfile() async {
    try {
      final response = await _remote.getCurrentUser();
      await _local.saveUser(response.user);
      await _local.savePermissions(response.permissions);
      return (user: response.user, permissions: response.permissions, error: null);
    } on Failure catch (e) {
      return (user: null, permissions: null, error: e);
    } catch (e) {
      return (user: null, permissions: null, error: UnknownFailure(message: e.toString()));
    }
  }

  /// Whether the user is authenticated (has a stored token).
  bool get isAuthenticated => _local.isAuthenticated;

  /// Gets the stored user.
  UserModel? get currentUser => _local.getUser();

  /// Gets the stored permissions.
  List<String> get permissions => _local.getPermissions();

  /// Collects device info for the auth token.
  Future<_DeviceInfo> _getDeviceInfo() async {
    final deviceInfo = DeviceInfoPlugin();
    String type;
    String id;
    String userAgent;

    if (Platform.isAndroid) {
      final info = await deviceInfo.androidInfo;
      type = 'android';
      id = info.id;
      userAgent = 'FitNationApp/Android ${info.version.release} (${info.model})';
    } else if (Platform.isIOS) {
      final info = await deviceInfo.iosInfo;
      type = 'ios';
      id = info.identifierForVendor ?? 'unknown';
      userAgent = 'FitNationApp/iOS ${info.systemVersion} (${info.model})';
    } else {
      type = 'web';
      id = 'unknown';
      userAgent = 'FitNationApp/Other';
    }

    return _DeviceInfo(type: type, id: id, userAgent: userAgent);
  }
}

class _DeviceInfo {
  final String type;
  final String id;
  final String userAgent;

  _DeviceInfo({required this.type, required this.id, required this.userAgent});
}