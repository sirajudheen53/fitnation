import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Zero-tap OTP delivery from WhatsApp (Android only).
///
/// Complements — never replaces — the backend HTTP OTP chain: this service
/// only starts the WhatsApp handshake and listens for code broadcasts. A
/// broadcast code is filled into the OTP screen and verified by the backend
/// exactly like a manually typed one; when no broadcast arrives, manual entry
/// keeps working unchanged.
class WhatsAppOtpService {
  static const MethodChannel _methodChannel = MethodChannel(
    'com.getfitwithus.app/whatsapp_otp',
  );
  static const EventChannel _eventChannel = EventChannel(
    'com.getfitwithus.app/whatsapp_otp/events',
  );

  /// Whether an installed WhatsApp client supports the zero-tap handshake.
  ///
  /// Always false on non-Android platforms; platform errors degrade to false
  /// so callers never have to handle failures.
  Future<bool> isHandshakeSupported() async {
    if (defaultTargetPlatform != TargetPlatform.android) return false;
    try {
      return await _methodChannel.invokeMethod<bool>('isHandshakeSupported') ??
          false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  /// Starts the zero-tap handshake with WhatsApp. Best-effort and never
  /// throws: on failure WhatsApp simply falls back to its one-tap autofill /
  /// copy-code UI and the user reads the code manually.
  Future<void> startHandshake() async {
    if (defaultTargetPlatform != TargetPlatform.android) return;
    try {
      await _methodChannel.invokeMethod<void>('startHandshake');
    } on PlatformException {
      // Handshake failed — manual entry keeps working.
    } on MissingPluginException {
      // Native side not available (tests).
    }
  }

  /// Stream of OTP codes broadcast by WhatsApp after a successful handshake.
  ///
  /// Non-string or empty events are filtered out; channel errors (including
  /// the missing-plugin error on unsupported environments) surface as stream
  /// errors the caller can ignore — manual code entry keeps working.
  Stream<String> codeStream() {
    if (defaultTargetPlatform != TargetPlatform.android) {
      return const Stream.empty();
    }
    return _eventChannel
        .receiveBroadcastStream()
        .map((event) => event is String ? event : '')
        .where((code) => code.isNotEmpty);
  }
}
