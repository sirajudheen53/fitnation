import 'dart:async';

import 'package:dio/dio.dart';

import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/notifications/data/data_sources/device_remote_data_source.dart';
import 'package:fitnation_app/features/notifications/services/messaging_client.dart';
import 'package:fitnation_app/features/notifications/services/push_notification_service.dart';

/// A messaging client that answers from a script.
class _FakeMessagingClient implements MessagingClient {
  _FakeMessagingClient();

  String? token = 'fcm-token-1';
  bool permissionGranted = true;
  final StreamController<String> tokenRefresh =
      StreamController<String>.broadcast();
  final StreamController<PushMessage> taps =
      StreamController<PushMessage>.broadcast();
  PushMessage? initialMessage;

  int registerCalls = 0;
  int permissionCalls = 0;

  @override
  Future<bool> requestPermission() async {
    permissionCalls++;
    return permissionGranted;
  }

  @override
  Future<String?> getToken() async {
    registerCalls++;
    return token;
  }

  @override
  Stream<String> get onTokenRefresh => tokenRefresh.stream;

  @override
  Stream<PushMessage> get onMessageTap => taps.stream;

  @override
  Future<PushMessage?> getInitialMessage() async => initialMessage;
}

/// Records what was registered with the backend.
class _RecordingDeviceSource extends DeviceRemoteDataSource {
  _RecordingDeviceSource() : super(Dio());

  final List<({String token, String deviceId, String platform})> registrations =
      <({String token, String deviceId, String platform})>[];
  final List<String> unregistrations = <String>[];

  @override
  Future<void> register({
    required String token,
    required String deviceId,
    required String platform,
    String deviceType = 'android',
  }) async {
    registrations.add((token: token, deviceId: deviceId, platform: platform));
  }

  @override
  Future<void> unregister(String token) async {
    unregistrations.add(token);
  }
}

void main() {
  late _RecordingDeviceSource devices;
  late _FakeMessagingClient messaging;

  setUp(() {
    devices = _RecordingDeviceSource();
    messaging = _FakeMessagingClient();
  });

  tearDown(() async {
    await messaging.tokenRefresh.close();
    await messaging.taps.close();
  });

  group('initialize', () {
    test('registers the current token with the backend', () async {
      final service = PushNotificationService(
        devices: devices,
        messaging: messaging,
      );

      await service.initialize();

      expect(messaging.permissionCalls, 1);
      expect(devices.registrations, hasLength(1));
      expect(devices.registrations.first.token, 'fcm-token-1');
      expect(devices.registrations.first.platform, 'android');
    });

    test('no-ops when Firebase is unavailable (no google-services.json)', () async {
      final service = PushNotificationService(devices: devices);

      await service.initialize();
      await service.registerCurrentToken();
      await service.unregisterCurrentToken();

      expect(service.isEnabled, isFalse);
      expect(devices.registrations, isEmpty);
      expect(devices.unregistrations, isEmpty);
    });

    test('a denied notification permission does not block registration', () async {
      messaging.permissionGranted = false;
      final service = PushNotificationService(
        devices: devices,
        messaging: messaging,
      );

      await service.initialize();

      // Registration is best-effort and independent of the permission.
      expect(devices.registrations, hasLength(1));
    });

    test('a failing registration is swallowed', () async {
      final service = PushNotificationService(
        devices: _ThrowingDeviceSource(),
        messaging: messaging,
      );

      // Must not throw.
      await service.initialize();
    });

    test('a failing messaging client is swallowed (push stays disabled)',
        () async {
      // The Firebase SDK can throw on a broken installation (a dev build
      // with a stale google-services.json, a revoked API key). The app must
      // still boot — push is best-effort.
      final service = PushNotificationService(
        devices: devices,
        messaging: _ThrowingMessagingClient(),
      );

      // Must not throw.
      await service.initialize();
      expect(devices.registrations, isEmpty);
    });
  });

  group('token rotation', () {
    test('a rotated token is registered again', () async {
      final service = PushNotificationService(
        devices: devices,
        messaging: messaging,
      );
      await service.initialize();
      expect(devices.registrations, hasLength(1));

      messaging.tokenRefresh.add('fcm-token-2');
      await Future<void>.delayed(Duration.zero);

      expect(devices.registrations, hasLength(2));
      expect(devices.registrations.last.token, 'fcm-token-2');
    });
  });

  group('logout', () {
    test('unregisters the token that was registered', () async {
      final service = PushNotificationService(
        devices: devices,
        messaging: messaging,
      );
      await service.initialize();

      await service.unregisterCurrentToken();

      expect(devices.unregistrations, ['fcm-token-1']);
    });

    test('unregistering twice only removes it once', () async {
      final service = PushNotificationService(
        devices: devices,
        messaging: messaging,
      );
      await service.initialize();

      await service.unregisterCurrentToken();
      await service.unregisterCurrentToken();

      expect(devices.unregistrations, ['fcm-token-1']);
    });

    test('a failing unregister is swallowed — logout still completes',
        () async {
      // The logout path must never be blocked by a push-cleanup failure:
      // the member has to get signed out either way.
      final service = PushNotificationService(
        devices: _ThrowingUnregisterSource(),
        messaging: messaging,
      );
      await service.initialize();

      // Must not throw.
      await service.unregisterCurrentToken();
    });
  });

  group('notification taps', () {
    test('a tap navigates to the route in the payload', () async {
      final navigated = <String>[];
      final service = PushNotificationService(
        devices: devices,
        messaging: messaging,
        onNavigate: navigated.add,
      );
      await service.initialize();

      messaging.taps.add(
        const PushMessage(data: {'route': '/workouts'}),
      );
      await Future<void>.delayed(Duration.zero);

      expect(navigated, ['/workouts']);
    });

    test('a known message type maps to its screen', () async {
      final navigated = <String>[];
      final service = PushNotificationService(
        devices: devices,
        messaging: messaging,
        onNavigate: navigated.add,
      );
      await service.initialize();

      messaging.taps.add(
        const PushMessage(data: {'type': 'membership_expiry'}),
      );
      await Future<void>.delayed(Duration.zero);

      expect(navigated, ['/profile/membership']);
    });

    test('a message with no route is ignored', () async {
      final navigated = <String>[];
      final service = PushNotificationService(
        devices: devices,
        messaging: messaging,
        onNavigate: navigated.add,
      );
      await service.initialize();

      messaging.taps.add(const PushMessage(data: {'foo': 'bar'}));
      await Future<void>.delayed(Duration.zero);

      expect(navigated, isEmpty);
    });

    test('a cold-start message routes on initialize', () async {
      final navigated = <String>[];
      messaging.initialMessage =
          const PushMessage(data: {'route': '/dashboard'});
      final service = PushNotificationService(
        devices: devices,
        messaging: messaging,
        onNavigate: navigated.add,
      );

      await service.initialize();

      expect(navigated, ['/dashboard']);
    });
  });
}

/// A device source whose registration always fails.
class _ThrowingDeviceSource extends DeviceRemoteDataSource {
  _ThrowingDeviceSource() : super(Dio());

  @override
  Future<void> register({
    required String token,
    required String deviceId,
    required String platform,
    String deviceType = 'android',
  }) async {
    throw StateError('network down');
  }
}

/// A device source whose unregistration always fails.
class _ThrowingUnregisterSource extends DeviceRemoteDataSource {
  _ThrowingUnregisterSource() : super(Dio());

  @override
  Future<void> register({
    required String token,
    required String deviceId,
    required String platform,
    String deviceType = 'android',
  }) async {}

  @override
  Future<void> unregister(String token) async {
    throw StateError('network down');
  }
}

/// A messaging client whose SDK calls always fail.
class _ThrowingMessagingClient implements MessagingClient {
  @override
  Future<bool> requestPermission() async => throw StateError('no Firebase');

  @override
  Future<String?> getToken() async => throw StateError('no Firebase');

  @override
  Stream<String> get onTokenRefresh => const Stream<String>.empty();

  @override
  Stream<PushMessage> get onMessageTap => const Stream<PushMessage>.empty();

  @override
  Future<PushMessage?> getInitialMessage() async =>
      throw StateError('no Firebase');
}
