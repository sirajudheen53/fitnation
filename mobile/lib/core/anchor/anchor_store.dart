import 'package:hive/hive.dart';

/// Persisted gym anchor (FBOS-011 §7.1 "AnchorStore").
///
/// Precedence (documented decision, brief deliverable 1):
///
/// 1. **Runtime anchor** — captured from an invite/join link, the Play
///    install referrer, or a gym code. Wins over everything because a member
///    may install from one gym's link and later join another gym.
/// 2. **Build-time anchor** — `--dart-define=GYM_ANCHOR=<tenant-uuid>`
///    ([AppEnvironment.gymAnchor]). Applies when no runtime anchor was ever
///    captured (per-gym build distributed off-Play).
/// 3. **No anchor** — phone-first auto-pin on the backend resolves
///    single-gym deployments (`apps/users/services.py`).
///
/// The runtime anchor is intentionally **sticky**: it survives logout (an
/// invite link pins the device, not the session) and is only replaced when a
/// *new* link/referrer/code is captured.
class AnchorStore {
  /// Creates a store. In production [init] opens the Hive box; tests may
  /// inject a [box].
  AnchorStore({Box<String>? box}) : _box = box;

  static const String boxName = 'anchor_box';
  static const String _gymUuidKey = 'runtime_gym_uuid';
  static const String _inviteTokenKey = 'runtime_invite_token';

  Box<String>? _box;

  /// Opens (or reuses) the Hive box. Safe to call multiple times.
  Future<void> init() async {
    _box ??= await Hive.openBox<String>(boxName);
  }

  Box<String> get _store => _box ??= Hive.box<String>(boxName);

  /// The runtime anchor captured on this device, or null.
  String? get runtimeGymUuid => _store.get(_gymUuidKey);

  /// The invite token from the captured link, or null.
  String? get inviteToken => _store.get(_inviteTokenKey);

  /// Persists a captured runtime anchor (link / referrer / gym code).
  Future<void> save({required String gymUuid, String? inviteToken}) async {
    await _store.put(_gymUuidKey, gymUuid);
    if (inviteToken != null && inviteToken.isNotEmpty) {
      await _store.put(_inviteTokenKey, inviteToken);
    }
  }

  /// Removes the runtime anchor (rarely used — the anchor is device-bound).
  Future<void> clear() async {
    await _store.delete(_gymUuidKey);
    await _store.delete(_inviteTokenKey);
  }

  /// The anchor to send on OTP calls: runtime wins over build-time.
  String? effectiveAnchor({String? buildTimeAnchor}) {
    final runtime = runtimeGymUuid;
    if (runtime != null && runtime.isNotEmpty) return runtime;
    if (buildTimeAnchor != null && buildTimeAnchor.isNotEmpty) {
      return buildTimeAnchor;
    }
    return null;
  }
}
