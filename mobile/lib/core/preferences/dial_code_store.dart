import 'package:hive/hive.dart';

import '../utils/country_code.dart';

/// Persisted "last selected dial code" for the phone input (issue #69).
///
/// Intentionally sticky like the gym anchor: remembering the member's
/// country is a preference, not session state — it survives app restarts
/// and logout. Nothing else is stored in the box.
class DialCodeStore {
  /// Creates a store. In production [init] opens the Hive box; tests may
  /// inject a [box].
  DialCodeStore({this.box});

  static const String boxName = 'dial_code_box';
  static const String _isoKey = 'last_dial_code_iso';

  Box<String>? box;

  /// Opens (or reuses) the Hive box. Safe to call multiple times.
  Future<void> init() async {
    box ??= await Hive.openBox<String>(boxName);
  }

  /// The remembered country, or null when nothing was saved yet (or the
  /// saved code is no longer in the supported list).
  CountryCode? load() {
    final iso = box?.get(_isoKey);
    return CountryCodes.findByIso(iso);
  }

  /// Remembers [country] as the last selection.
  Future<void> save(CountryCode country) async {
    await box?.put(_isoKey, country.code);
  }
}
