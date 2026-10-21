import 'dart:async';

import 'package:flutter/foundation.dart';

import '../data/data_sources/device_remote_data_source.dart';
import 'messaging_client.dart';

/// Registers the FCM token with the backend and routes notification taps
/// (FBOS-011 §7.4).
///
/// Lifecycle:
/// - `initialize()` on app start — registers the current token (if any),
///   re-registers on rotation, and forwards taps to [onNavigate].
/// - `registerCurrentToken()` again after every successful login (the token
///   must be bound to the freshly authenticated user).
/// - `unregisterCurrentToken()` on logout.
///
/// All failures are swallowed (best-effort plumbing — a push-registration
/// outage must never block the member from using the app).
class PushNotificationService {
  PushNotificationService({
    required DeviceRemoteDataSource devices,
    MessagingClient? messaging,
    Future<String> Function()? deviceId,
    void Function(String route)? onNavigate,
  })  : _devices = devices,
        _messaging = messaging,
        _deviceId = deviceId,
        onNavigate = onNavigate;

  final DeviceRemoteDataSource _devices;
  final MessagingClient? _messaging;
  final Future<String> Function()? _deviceId;

  /// Called when a notification tap should land on an in-app route.
  final void Function(String route)? onNavigate;

  StreamSubscription<String>? _refreshSub;
  StreamSubscription<PushMessage>? _tapSub;
  String? _lastRegisteredToken;

  /// Whether push plumbing is active (messaging client available + ready).
  bool get isEnabled => _messaging != null;

  /// Wires token registration and tap routing. Safe to call when Firebase is
  /// unavailable (no `google-services.json`) — everything no-ops.
  Future<void> initialize() async {
    final messaging = _messaging;
    if (messaging == null) {
      debugPrint('PushNotificationService: messaging unavailable — push disabled');
      return;
    }

    try {
      final granted = await messaging.requestPermission();
      if (!granted) {
        debugPrint('PushNotificationService: permission not granted');
      }
      await registerCurrentToken();

      _refreshSub = messaging.onTokenRefresh.listen((token) {
        _register(token);
      });
      _tapSub = messaging.onMessageTap.listen((message) {
        _route(message);
      });
      final initial = await messaging.getInitialMessage();
      if (initial != null) _route(initial);
    } catch (e) {
      debugPrint('PushNotificationService: init failed (push disabled): $e');
    }
  }

  /// Registers the current FCM token against the authenticated user.
  Future<void> registerCurrentToken() async {
    final messaging = _messaging;
    if (messaging == null) return;
    try {
      final token = await messaging.getToken();
      if (token == null || token.isEmpty) return;
      await _register(token);
    } catch (e) {
      debugPrint('PushNotificationService: register failed: $e');
    }
  }

  /// Removes this device's backend registration (logout path).
  Future<void> unregisterCurrentToken() async {
    final token = _lastRegisteredToken;
    if (token == null) return;
    _lastRegisteredToken = null;
    try {
      await _devices.unregister(token);
    } catch (e) {
      debugPrint('PushNotificationService: unregister failed: $e');
    }
  }

  Future<void> _register(String token) async {
    try {
      final id = _deviceId != null ? await _deviceId() : '';
      await _devices.register(
        token: token,
        deviceId: id,
        platform: 'android',
      );
      _lastRegisteredToken = token;
    } catch (e) {
      debugPrint('PushNotificationService: token registration failed: $e');
    }
  }

  void _route(PushMessage message) {
    final route = message.resolveRoute();
    if (route != null) onNavigate?.call(route);
  }

  Future<void> dispose() async {
    await _refreshSub?.cancel();
    await _tapSub?.cancel();
    _refreshSub = null;
    _tapSub = null;
  }
}
