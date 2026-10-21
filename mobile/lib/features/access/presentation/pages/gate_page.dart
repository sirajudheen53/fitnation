import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../auth/presentation/providers/auth_notifier.dart';

/// The app-access gate (FBOS-011 §3.4, §7.2).
///
/// Full-screen stop for members whose entitlement is `expired` (grace over)
/// or `none` (never a member / plan without app access / tenant flag off).
/// Never a crash, never a blank dashboard: friendly copy + what to do.
///
/// `grace` (read-only) does NOT land here — those members keep the app with a
/// persistent [GraceBanner] and disabled writes.
class GatePage extends ConsumerStatefulWidget {
  const GatePage({super.key});

  @override
  ConsumerState<GatePage> createState() => _GatePageState();
}

class _GatePageState extends ConsumerState<GatePage> {
  bool _refreshing = false;

  Future<void> _refresh() async {
    setState(() => _refreshing = true);
    await ref.read(authProvider.notifier).refreshEntitlement();
    if (mounted) setState(() => _refreshing = false);
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    final entitlement = auth.entitlement;
    final gymName = entitlement?.gymName ?? auth.user?.tenantName ?? 'your gym';

    // `expired` and `none` need different copy (FBOS-011 §3.4).
    final isExpired = entitlement?.status == AppEntitlementStatus.expired;

    return Scaffold(
      backgroundColor: AppTheme.background,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Card(
                color: AppTheme.surface,
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(24),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(28),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Icon(
                        isExpired ? Icons.event_busy_rounded : Icons.lock_outline_rounded,
                        size: 56,
                        color: AppTheme.primary,
                      ),
                      const SizedBox(height: 20),
                      Text(
                        isExpired
                            ? 'Your membership has expired'
                            : 'Welcome to $gymName!',
                        style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                              fontWeight: FontWeight.w800,
                            ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        isExpired
                            ? 'Your membership expired on '
                                '${_formatDate(entitlement?.endDate)}. '
                                'Renew at $gymName to get back into your '
                                'workouts, diet plans and progress.'
                            : 'Your membership doesn\u2019t include the '
                                'FitNation app yet. Ask the front desk at '
                                '$gymName to set you up \u2014 it takes a minute.',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: AppTheme.textSecondary,
                              height: 1.5,
                            ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 28),
                      ElevatedButton.icon(
                        onPressed: _refreshing ? null : _refresh,
                        icon: _refreshing
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                strokeWidth: 2,
                                child: CircularProgressIndicator(color: Colors.white),
                              )
                            : const Icon(Icons.refresh_rounded),
                        label: Text(_refreshing ? 'Checking…' : 'I\u2019ve renewed — refresh'),
                      ),
                      const SizedBox(height: 12),
                      TextButton(
                        onPressed: () =>
                            ref.read(authProvider.notifier).logout(),
                        child: const Text('Log out'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  static String _formatDate(DateTime? date) {
    if (date == null) return 'your last active day';
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    return '${date.day} ${months[date.month - 1]} ${date.year}';
  }
}
