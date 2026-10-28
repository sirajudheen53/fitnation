import 'package:flutter/material.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../attendance/presentation/providers/check_in_providers.dart';

/// Home card showing the member's check-in state (issue #95).
///
/// One of the essentials: whether they are in the gym right now, when they
/// last visited, or that there is no history yet. Carries its own compact
/// loading / error / empty state so it never blocks the rest of the home.
class CheckInStatusCard extends StatelessWidget {
  final CheckInState state;
  final Future<void> Function() onRetry;

  const CheckInStatusCard({
    super.key,
    required this.state,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final summary = state.summary;

    if (summary == null && state.status == CheckInStatus.loading) {
      return _frame(
        const Row(
          children: [
            SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            SizedBox(width: 12),
            Expanded(
              child: Text(
                'Checking your visit status…',
                style: TextStyle(color: AppTheme.textSecondary, fontSize: 14),
              ),
            ),
          ],
        ),
      );
    }

    if (summary == null && state.status == CheckInStatus.error) {
      return _frame(
        Row(
          children: [
            const Icon(Icons.cloud_off_outlined,
                size: 20, color: AppTheme.textSecondary),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                state.errorMessage ?? 'Couldn\'t load your check-ins.',
                style: const TextStyle(
                    color: AppTheme.textSecondary, fontSize: 14),
              ),
            ),
            TextButton(onPressed: onRetry, child: const Text('Retry')),
          ],
        ),
      );
    }

    if (summary == null || summary.latest == null) {
      return _frame(
        const _StateRow(
          icon: Icons.event_available_outlined,
          title: 'No visits yet',
          subtitle: 'Your check-ins will show up here.',
        ),
      );
    }

    if (summary.isCheckedIn) {
      final visit = summary.active!;
      return _frame(
        _StateRow(
          icon: Icons.event_available,
          iconColor: const Color(0xFF00996E),
          dotColor: AppTheme.accent,
          title: 'You\'re checked in',
          subtitle: visit.branchName == null
              ? 'Since ${formatTimeShort(visit.checkInTime)}'
              : 'Since ${formatTimeShort(visit.checkInTime)} at ${visit.branchName}',
        ),
      );
    }

    final visit = summary.lastCompleted!;
    return _frame(
      _StateRow(
        icon: Icons.event_available_outlined,
        title: 'Last visit ${formatDateShort(visit.checkInTime)}',
        subtitle: visit.checkOutIsAuto
            ? 'Checked out automatically at ${formatTimeShort(visit.checkOutTime!)}'
            : 'Checked out at ${formatTimeShort(visit.checkOutTime!)}',
      ),
    );
  }

  Widget _frame(Widget child) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.divider),
      ),
      child: child,
    );
  }
}

class _StateRow extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final Color? dotColor;
  final String title;
  final String subtitle;

  const _StateRow({
    required this.icon,
    this.iconColor = AppTheme.primary,
    this.dotColor,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: iconColor.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(icon, color: iconColor, size: 22),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  if (dotColor != null) ...[
                    Container(
                      width: 8,
                      height: 8,
                      decoration:
                          BoxDecoration(color: dotColor, shape: BoxShape.circle),
                    ),
                    const SizedBox(width: 6),
                  ],
                  Flexible(
                    child: Text(
                      title,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                style: const TextStyle(
                    fontSize: 13, color: AppTheme.textSecondary),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
