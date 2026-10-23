import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'dial_code_store.dart';

/// The app-wide dial-code preference store. The instance is created in
/// `main` after Hive init and injected via [ProviderScope] overrides.
///
/// Reading it before the override is installed throws, so callers that must
/// tolerate a missing store (widget tests, early boot) should use
/// [dialCodeStoreOrNull] instead.
final dialCodeStoreProvider = Provider<DialCodeStore>((ref) {
  throw UnimplementedError('dialCodeStoreProvider must be overridden in main');
});

/// The dial-code store, or null when it has not been wired.
///
/// The store is a convenience, not a requirement: without it the phone
/// input still works, it just always starts on the default (+91 India).
final dialCodeStoreOrNull = Provider<DialCodeStore?>((ref) {
  try {
    return ref.watch(dialCodeStoreProvider);
  } on UnimplementedError {
    return null;
  }
});
