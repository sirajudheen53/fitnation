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
  Future<String?> getToken() => FirebaseMessaging.instance.getToken();

  @override
  Stream<String> get onTokenRefresh => FirebaseMessaging.instance.onTokenRefresh;

  @override
  Stream<PushMessage> get onMessageTap =>
      FirebaseMessaging.instance.onMessageOpenedApp
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
    return FirebaseMessagingClient();
  } catch (e) {
    // FirebaseException: no default options (google-services.json missing).
    return null;
  }
}
