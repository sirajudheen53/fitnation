import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'anchor_store.dart';

/// The app-wide gym-anchor store. The instance is created in `main` after
/// Hive init and injected via [ProviderScope] overrides.
///
/// Reading it before the override is installed throws, so callers that must
/// tolerate a missing store (unit tests, early boot) should use
/// [anchorStoreOrNull] instead.
final anchorStoreProvider = Provider<AnchorStore>((ref) {
  throw UnimplementedError('anchorStoreProvider must be overridden in main');
});

/// The gym-anchor store, or null when it has not been wired.
///
/// The anchor is an optimisation, not a requirement: without it the backend
/// falls back to phone-first auto-pin, so a missing store must never break
/// the login flow.
final anchorStoreOrNullProvider = Provider<AnchorStore?>((ref) {
  try {
    return ref.watch(anchorStoreProvider);
  } on UnimplementedError {
    return null;
  }
});
