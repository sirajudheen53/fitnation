import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'anchor_store.dart';

/// The app-wide gym-anchor store. The instance is created in `main` after
/// Hive init and injected via [ProviderScope] overrides.
final anchorStoreProvider = Provider<AnchorStore>((ref) {
  throw UnimplementedError('anchorStoreProvider must be overridden in main');
});
