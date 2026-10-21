import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/data/data_sources/api_client.dart';
import '../data/data_sources/device_remote_data_source.dart';
import '../services/messaging_client.dart';
import '../services/push_notification_service.dart';

/// Provides the device-token remote data source.
final deviceRemoteDataSourceProvider = Provider<DeviceRemoteDataSource>((ref) {
  return DeviceRemoteDataSource(ApiClient.getInstance());
});

/// The messaging client, or null when Firebase is unavailable (no
/// `google-services.json` in dev builds — push is simply disabled,
/// FBOS-011 M4). Overridden in `main.dart` after a successful
/// `Firebase.initializeApp()`.
final messagingClientProvider = Provider<MessagingClient?>((ref) => null);

/// Provides the push notification service.
final pushNotificationServiceProvider = Provider<PushNotificationService>((ref) {
  final messaging = ref.watch(messagingClientProvider);
  return PushNotificationService(
    devices: ref.watch(deviceRemoteDataSourceProvider),
    messaging: messaging,
  );
});

/// [MessagingClient] backed by Firebase Cloud Messaging (Android).
class FirebaseMessagingClient implements MessagingClient {
  @override
  Future<bool> requestPermission() async {
    final settings = await FirebaseMessaging.instance.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );
    return settings.authorizationStatus == AuthorizationStatus.authorized ||
        settings.authorizationStatus == AuthorizationStatus.provisional;
  }

  @override
  Future<String?> getToken() async {
    // FCM v17: the FID arrives on the `onRegistered` stream, not from a
    // synchronous getter. `register()` asks Firebase to (re)register this
    // installation; the resulting FID is delivered on `onRegistered`.
    //
    // The stream must be subscribed to *before* `register()` is called:
    // `onRegistered` is a broadcast stream, so an FID delivered in between
    // would be dropped.
    final registered = FirebaseMessaging.instance.onRegistered.first;
    try {
      await FirebaseMessaging.instance.register();
    } catch (e) {
      return null;
    }
    return registered.timeout(
      const Duration(seconds: 10),
      onTimeout: () => '',
    );
  }

  @override
  Stream<String> get onTokenRefresh => FirebaseMessaging.instance.onRegistered;

  @override
  Stream<PushMessage> get onMessageTap =>
      FirebaseMessaging.onMessageOpenedApp
          .map((message) => PushMessage(data: message.data));

  @override
  Future<PushMessage?> getInitialMessage() async {
    final message = await FirebaseMessaging.instance.getInitialMessage();
    return message == null ? null : PushMessage(data: message.data);
  }
}

/// Initializes Firebase when a default app is configured. Returns the client
/// (or null) so `main.dart` can override [messagingClientProvider]. Never
/// throws — a missing `google-services.json` degrades to "push disabled".
Future<MessagingClient?> bootstrapFirebase() async {
  try {
    await Firebase.initializeApp();
  } catch (e) {
    // FirebaseException: no default options (google-services.json missing).
    return null;
  }

  // `initializeApp` can succeed with a default (empty) configuration on
  // Android even without google-services.json, and the failure only shows up
  // when messaging is first used. Probe it here so a dev build without the
  // config file still boots — push is simply disabled.
  try {
    await FirebaseMessaging.instance.getInitialMessage();
    return FirebaseMessagingClient();
  } catch (e) {
    return null;
  }
}
