import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/preferences/dial_code_providers.dart';
import '../../../../core/utils/country_code.dart';

/// The dial code currently selected on the phone input (issue #69).
///
/// Seeds from the local preference store (last selection) and defaults to
/// India (+91) when nothing is remembered. Selections write through to the
/// store via the screen, so the next visit — and the next app start —
/// opens on the member's country.
final selectedCountryProvider = StateProvider<CountryCode>((ref) {
  final store = ref.watch(dialCodeStoreOrNull);
  return store?.load() ?? CountryCodes.defaultCode;
});
