import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../attendance/presentation/providers/check_in_providers.dart';
import '../../../auth/presentation/providers/auth_notifier.dart';
import '../../../memberships/presentation/providers/membership_providers.dart';
import '../../../payments/presentation/providers/payment_providers.dart';
import '../../../plans/presentation/providers/plan_assignment_providers.dart';
import '../widgets/check_in_status_card.dart';
import '../widgets/dues_card.dart';
import '../widgets/plans_summary_card.dart';

/// Home tab — the consolidated member homepage (issue #95).
///
/// One scrollable screen with the essentials only: check-in state, current
/// membership + pending dues, and the assigned plans (deep-linking into the
/// Workouts / Diet tabs). Every section owns its compact loading / error /
/// empty state so no single slow endpoint blocks the screen; pull down to
/// refresh everything at once.
class HomeTab extends ConsumerStatefulWidget {
  /// Opens the Workouts tab; null when the member lacks the permission.
  final VoidCallback? onOpenWorkouts;

  /// Opens the Diet tab; null when the member lacks the permission.
  final VoidCallback? onOpenDiet;

  const HomeTab({super.key, this.onOpenWorkouts, this.onOpenDiet});

  @override
  ConsumerState<HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends ConsumerState<HomeTab> {
  @override
  void initState() {
    super.initState();
    // Deferred: load() writes state synchronously, which Riverpod forbids
    // during the build phase. All sections load in parallel.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _loadAll();
    });
  }

  Future<void> _loadAll() async {
    await Future.wait([
      ref.read(checkInProvider.notifier).load(),
      ref.read(membershipProvider.notifier).load(),
      ref.read(pendingPaymentsProvider.notifier).load(),
      ref.read(workoutAssignmentsProvider.notifier).load(),
      ref.read(dietAssignmentsProvider.notifier).load(),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final checkIn = ref.watch(checkInProvider);
    final membership = ref.watch(membershipProvider);
    final dues = ref.watch(pendingPaymentsProvider);
    final workouts = ref.watch(workoutAssignmentsProvider);
    final diet = ref.watch(dietAssignmentsProvider);
    final user = ref.watch(authProvider).user;

    return RefreshIndicator(
      onRefresh: _loadAll,
      child: ListView(
        // Always scrollable so the pull-to-refresh works even when the
        // content is shorter than the screen.
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(24, 16, 24, 24),
        children: [
          Text(
            'Welcome back,',
            style: TextStyle(
                color: AppTheme.textSecondary.withValues(alpha: 0.8),
                fontSize: 14),
          ),
          const SizedBox(height: 4),
          Text(
            user?.fullName ?? 'Athlete',
            style: const TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
          if (user?.tenantName != null) ...[
            const SizedBox(height: 2),
            Text(
              user!.tenantName!,
              style: const TextStyle(
                  fontSize: 13, color: AppTheme.textSecondary),
            ),
          ],
          const SizedBox(height: 20),
          CheckInStatusCard(
            state: checkIn,
            onRetry: () => ref.read(checkInProvider.notifier).load(),
          ),
          const SizedBox(height: 12),
          DuesCard(
            membership: membership,
            dues: dues,
            onRetry: () async {
              await Future.wait([
                ref.read(membershipProvider.notifier).load(),
                ref.read(pendingPaymentsProvider.notifier).load(),
              ]);
            },
          ),
          const SizedBox(height: 12),
          PlansSummaryCard(
            workouts: workouts,
            diet: diet,
            onOpenWorkouts: widget.onOpenWorkouts,
            onOpenDiet: widget.onOpenDiet,
          ),
        ],
      ),
    );
  }
}
