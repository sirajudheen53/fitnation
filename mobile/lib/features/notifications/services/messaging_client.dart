/// Platform-agnostic push-messaging surface (FBOS-011 §7.4).
///
/// Wraps Firebase Cloud Messaging behind an interface so the registration /
/// routing logic is unit-testable without the Firebase SDK, and so the app
/// boots cleanly on devices/builds without `google-services.json`
/// (FBOS-011 M4: "no crash without google-services.json in dev").
library;

/// A push message's payload, normalized for routing.
class PushMessage {
  const PushMessage({required this.data});

  final Map<String, dynamic> data;

  /// The in-app route this message points at. The backend contract (v1):
  /// `data.route` wins; `data.type` falls back to known screens —
  /// `membership_expiry` → `/profile/membership`.
  String? resolveRoute() {
    final route = data['route'];
    if (route is String && route.startsWith('/')) return route;
    final type = data['type'];
    if (type == 'membership_expiry') return '/profile/membership';
    return null;
  }
}

/// What the app needs from the messaging SDK — implemented by
/// `FirebaseMessagingClient` (see providers) and faked in tests.
abstract class MessagingClient {
  /// Asks for notification permission (Android 13+ POST_NOTIFICATIONS) and
  /// prepares the SDK. Returns false when the user declined / unavailable.
  Future<bool> requestPermission();

  /// The current FCM registration token (null when unavailable).
  Future<String?> getToken();

  /// Fires when FCM rotates the registration token.
  Stream<String> get onTokenRefresh;

  /// Fires when the user taps a notification (app in background).
  Stream<PushMessage> get onMessageTap;

  /// The message that launched the app from terminated state (cold-start
  /// notification tap), or null.
  Future<PushMessage?> getInitialMessage();
}
