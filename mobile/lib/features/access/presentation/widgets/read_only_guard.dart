import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/presentation/providers/auth_notifier.dart';
import 'grace_banner.dart';

/// Blocks write actions while the member is in the read-only grace window
/// (FBOS-011 §3.4).
///
/// The banner is informational; the *writes* are what must stop. The guard
/// swaps the button's own `onPressed` for one that explains why the action
/// is blocked, so the button keeps its look instead of silently going dead.
class ReadOnlyGuard extends ConsumerWidget {
  const ReadOnlyGuard({
    super.key,
    required this.builder,
    required this.onPressed,
    this.enabled = true,
  });

  /// Builds the action, given the (possibly replaced) callback.
  final Widget Function(VoidCallback? onPressed) builder;

  /// The action to run when the member is allowed to write.
  final VoidCallback? onPressed;

  /// Whether the action is allowed for other reasons (e.g. a busy form).
  final bool enabled;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isReadOnly = ref.watch(authProvider).isReadOnlyGrace;

    if (!isReadOnly) {
      return builder(enabled ? onPressed : null);
    }

    return builder(() {
      showReadOnlySnack(context);
    });
  }
}

/// Whether write actions are currently blocked (read-only grace).
///
/// Screens that need to branch on it (rather than wrap a single button)
/// can read this directly.
bool isReadOnlyGrace(WidgetRef ref) => ref.read(authProvider).isReadOnlyGrace;
