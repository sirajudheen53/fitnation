/// Gym-anchored join links (FBOS-011 §5.4 / §7.3).
///
/// The invite carries the gym anchor so the app can pin OTP logins to the
/// inviting gym without any typing. Two link shapes are supported (the
/// app-link domain is `app.yougetfitwithus.com`, FBOS-011 D7; the brief's
/// `/join?gym=` shape on the API host is kept for compatibility):
///
/// - App Link:  `https://app.yougetfitwithus.com/g/{tenant-uuid}`
///              `https://api.yougetfitwithus.com/join?gym={tenant-uuid}&t={token}`
/// - Custom:    `fitnation://g/{tenant-uuid}`
///              `fitnation://join?gym={tenant-uuid}&t={token}`
library;

/// How a [JoinLink] reached the app.
enum JoinLinkSource {
  /// Verified https App Link (or plain https tap — Android routes both here).
  appLink,

  /// `fitnation://` custom scheme (unverified; used as a fallback).
  customScheme,
}

/// A parsed invite/join link carrying the gym anchor.
class JoinLink {
  const JoinLink({required this.gymUuid, this.inviteToken, required this.source});

  /// Tenant UUID of the inviting gym (the `gym` anchor for OTP calls).
  final String gymUuid;

  /// Optional invite token (`t` query parameter). Reserved for the
  /// server-side invite validation contract; captured and persisted so a
  /// later contract can use it without re-sending the link.
  final String? inviteToken;

  /// How the link reached the app.
  final JoinLinkSource source;

  /// Hosts whose https links we treat as join links.
  static const List<String> appLinkHosts = [
    'app.yougetfitwithus.com',
    'api.yougetfitwithus.com',
  ];

  /// The custom scheme handled by the AndroidManifest intent-filter.
  static const String customScheme = 'fitnation';

  static final RegExp _uuid = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
  );

  /// Parses [uri] into a [JoinLink], or returns null when the URI is not a
  /// join link (wrong scheme/host/path and no parseable gym anchor).
  static JoinLink? tryParse(Uri uri) {
    final source = _sourceOf(uri);
    if (source == null) return null;

    String? gym;
    String? token = uri.queryParameters['t'];

    if (uri.host == 'g') {
      // fitnation://g/{uuid}
      gym = uri.pathSegments.isNotEmpty ? uri.pathSegments.first : null;
    } else if (uri.host == 'join') {
      // fitnation://join?gym=…&t=…
      gym = uri.queryParameters['gym'];
    } else if (source == JoinLinkSource.appLink) {
      if (uri.pathSegments.length == 2 &&
          uri.pathSegments.first == 'g') {
        // https://app.yougetfitwithus.com/g/{uuid}
        gym = uri.pathSegments[1];
      } else if (uri.pathSegments.isNotEmpty && uri.pathSegments.first == 'join') {
        // https://api.yougetfitwithus.com/join?gym=…&t=…
        gym = uri.queryParameters['gym'];
      }
    }

    if (gym == null || !_uuid.hasMatch(gym)) return null;
    if (token != null && token.isEmpty) token = null;

    return JoinLink(gymUuid: gym.toLowerCase(), inviteToken: token, source: source);
  }

  /// Which transport [uri] arrived over, or null when it is not ours.
  static JoinLinkSource? _sourceOf(Uri uri) {
    if (uri.scheme == 'https' && appLinkHosts.contains(uri.host.toLowerCase())) {
      return JoinLinkSource.appLink;
    }
    if (uri.scheme == customScheme) {
      return JoinLinkSource.customScheme;
    }
    return null;
  }

  @override
  String toString() =>
      'JoinLink(gym: $gymUuid, token: ${inviteToken == null ? '—' : 'present'}, source: $source)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is JoinLink &&
          other.gymUuid == gymUuid &&
          other.inviteToken == inviteToken &&
          other.source == source;

  @override
  int get hashCode => Object.hash(gymUuid, inviteToken, source);
}
