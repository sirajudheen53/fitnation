import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/auth/services/whatsapp_otp_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const methodChannel = MethodChannel('com.getfitwithus.app/whatsapp_otp');
  // The messenger's handler registry is keyed by channel name, so a
  // MethodChannel with the event channel's name is how we mock the event
  // channel's listen/cancel protocol.
  const eventsChannelName = 'com.getfitwithus.app/whatsapp_otp/events';
  const eventsChannelForMocks = MethodChannel(eventsChannelName);
  final binding = TestDefaultBinaryMessengerBinding.instance;
  final service = WhatsAppOtpService();

  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
    binding.defaultBinaryMessenger.setMockMethodCallHandler(methodChannel, null);
    binding.defaultBinaryMessenger.setMockMethodCallHandler(
      eventsChannelForMocks,
      null,
    );
  });

  Future<void> pushEvent(Object? event) async {
    await binding.defaultBinaryMessenger.handlePlatformMessage(
      eventsChannelName,
      const StandardMethodCodec().encodeSuccessEnvelope(event),
      (ByteData? data) {},
    );
    await Future<void>.delayed(Duration.zero);
  }

  group('isHandshakeSupported', () {
    test('returns the native answer on Android', () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      binding.defaultBinaryMessenger.setMockMethodCallHandler(
        methodChannel,
        (call) async => call.method == 'isHandshakeSupported',
      );

      expect(await service.isHandshakeSupported(), isTrue);
    });

    test('returns false when no WhatsApp client supports the handshake', () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      binding.defaultBinaryMessenger.setMockMethodCallHandler(
        methodChannel,
        (call) async => false,
      );

      expect(await service.isHandshakeSupported(), isFalse);
    });

    test('degrades platform errors to false', () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      binding.defaultBinaryMessenger.setMockMethodCallHandler(
        methodChannel,
        (call) async => throw PlatformException(code: 'nope'),
      );

      expect(await service.isHandshakeSupported(), isFalse);
    });

    test('degrades a missing plugin to false', () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      // No mock handler -> MissingPluginException.

      expect(await service.isHandshakeSupported(), isFalse);
    });

    test('short-circuits on iOS without touching the channel', () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
      var channelCalled = false;
      binding.defaultBinaryMessenger.setMockMethodCallHandler(
        methodChannel,
        (call) async {
          channelCalled = true;
          return true;
        },
      );

      expect(await service.isHandshakeSupported(), isFalse);
      expect(channelCalled, isFalse);
    });
  });

  group('startHandshake', () {
    test('invokes the native handshake on Android', () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      final calls = <String>[];
      binding.defaultBinaryMessenger.setMockMethodCallHandler(
        methodChannel,
        (call) async {
          calls.add(call.method);
          return {'supported': true};
        },
      );

      await service.startHandshake();

      expect(calls, ['startHandshake']);
    });

    test('never throws on platform errors', () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      binding.defaultBinaryMessenger.setMockMethodCallHandler(
        methodChannel,
        (call) async => throw PlatformException(code: 'nope'),
      );

      await service.startHandshake();
    });

    test('never throws when the plugin is missing', () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      // No mock handler -> MissingPluginException.

      await service.startHandshake();
    });

    test('short-circuits on iOS without touching the channel', () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
      var channelCalled = false;
      binding.defaultBinaryMessenger.setMockMethodCallHandler(
        methodChannel,
        (call) async {
          channelCalled = true;
          return null;
        },
      );

      await service.startHandshake();

      expect(channelCalled, isFalse);
    });
  });

  group('codeStream', () {
    test('delivers string broadcasts on Android', () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      binding.defaultBinaryMessenger.setMockMethodCallHandler(
        eventsChannelForMocks,
        (call) async => null,
      );

      final codes = <String>[];
      final sub = service.codeStream().listen(
        codes.add,
        onError: (Object _) {},
        cancelOnError: true,
      );
      await Future<void>.delayed(Duration.zero);

      await pushEvent('654321');
      await pushEvent('');
      await pushEvent(123456); // non-string payloads are filtered

      expect(codes, ['654321']);
      await sub.cancel();
    });

    test('survives a missing plugin (stream just stays empty)', () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      // No mock handler -> listen fails with MissingPluginException.

      final codes = <String>[];
      final sub = service.codeStream().listen(
        codes.add,
        onError: (Object _) {},
        cancelOnError: false,
      );
      await Future<void>.delayed(Duration.zero);

      expect(codes, isEmpty);
      await sub.cancel();
    });

    test('is empty on iOS without listening to the channel', () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
      var channelListenAttempted = false;
      binding.defaultBinaryMessenger.setMockMethodCallHandler(
        eventsChannelForMocks,
        (call) async {
          channelListenAttempted = true;
          return null;
        },
      );

      final codes = <String>[];
      final sub = service.codeStream().listen(codes.add);
      await Future<void>.delayed(Duration.zero);

      expect(codes, isEmpty);
      expect(channelListenAttempted, isFalse);
      await sub.cancel();
    });
  });
}
