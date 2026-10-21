import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/foundation.dart';

import 'join_link.dart';
import '../anchor/anchor_store.dart';

/// Captures gym anchors from join links and the Play install referrer
/// (FBOS-011 §5.4 / §7.3).
///
/// Policy:
/// - Unauthenticated (first open after invite): the anchor is saved
///   immediately — the cold-start path included (Play re-delivers the deep
///   link on first launch; `getInitialLink()` covers it).
/// - Authenticated under the same gym: no-op.
/// - Authenticated under a *different* gym: [confirmSwitch] is asked before
///   overwriting (multi-gym members exist).
/// - Install referrer (`gym=<uuid>`): saved only when no runtime anchor is
///   stored yet — a real link always beats the referrer.
class DeepLinkService {
  DeepLinkService({
    required this.anchorStore,
    this.appLinks,
    this.readInstallReferrer,
    this.confirmSwitch,
  });

  final AnchorStore anchorStore;
  final AppLinks? appLinks;
  final Future<String?> Function()? readInstallReferrer;
  final Future<bool> Function(JoinLink link)? confirmSwitch;

  StreamSubscription<Uri>? _linkSubscription;

  /// Whether a runtime anchor already exists (referrer defers to it).
  bool get hasRuntimeAnchor =>
      anchorStore.runtimeGymUuid != null &&
      anchorStore.runtimeGymUuid!.isNotEmpty;

  /// The effective anchor to send on OTP calls (runtime wins over the
  /// build-time `--dart-define=GYM_ANCHOR`).
  String? effectiveAnchor(String buildTimeAnchor) =>
      anchorStore.effectiveAnchor(buildTimeAnchor: buildTimeAnchor);

  /// Starts listening: cold-start link (Play re-delivery), warm links, and
  /// (once) the Play install referrer.
  Future<void> init() async {
    await _captureInitialLink();
    await _captureInstallReferrerOnce();
    _listenForWarmLinks();
  }

  Future<void> _captureInitialLink() async {
    final links = appLinks;
    if (links == null) return;
    try {
      final initial = await links.getInitialLink();
      if (initial != null) await handleLink(initial);
    } catch (e) {
      debugPrint('DeepLinkService: initial link unavailable: $e');
    }
  }

  void _listenForWarmLinks() {
    final links = appLinks;
    if (links == null) return;
    _linkSubscription = links.uriLinkStream.listen(
      (uri) => handleLink(uri),
      onError: (Object e) => debugPrint('DeepLinkService: link stream error: $e'),
    );
  }

  Future<void> _captureInstallReferrerOnce() async {
    final read = readInstallReferrer;
    if (read == null) return;
    try {
      final raw = await read();
      if (raw != null) await handleInstallReferrer(raw);
    } catch (e) {
      debugPrint('DeepLinkService: install referrer unavailable: $e');
    }
  }

  /// Handles an incoming link URI. Returns true when an anchor was persisted.
  Future<bool> handleLink(Uri uri) async {
    final link = JoinLink.tryParse(uri);
    if (link == null) return false;
    return capture(link);
  }

  /// Persists [link] per the policy documented on this class.
  Future<bool> capture(JoinLink link) async {
    final confirm = confirmSwitch;
    if (confirm != null && !(await confirm(link))) {
      return false;
    }
    await anchorStore.save(
      gymUuid: link.gymUuid,
      inviteToken: link.inviteToken,
    );
    return true;
  }

  /// Parses a raw Play install referrer (`gym=<uuid>` after URL decoding,
  /// e.g. `gym%3D3f7c…`) and persists it when no runtime anchor exists yet.
  Future<bool> handleInstallReferrer(String raw) async {
    if (hasRuntimeAnchor) return false;
    final decoded = Uri.tryParse('https://placeholder/?$raw')?.queryParameters['gym'] ??
        _extractGymFallback(raw);
    if (decoded == null || decoded.isEmpty) return false;
    final normalized = decoded.trim().toLowerCase();
    final link = JoinLink.tryParse(
      Uri.parse('fitnation://join?gym=$normalized'),
    );
    if (link == null) return false;
    await anchorStore.save(gymUuid: link.gymUuid);
    return true;
  }

  Future<void> dispose() async {
    await _linkSubscription?.cancel();
    _linkSubscription = null;
  }
}

/// Lenient fallback for referrers that are not valid query strings.
String? _extractGymFallback(String raw) {
  final match = RegExp(r'gym[=:]([0-9a-fA-F-]{36})').firstMatch(raw);
  return match?.group(1);
}
