import 'package:flutter/material.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../auth/data/models/entitlement.dart';

/// Persistent amber banner shown while the member is in the read-only grace
/// window (FBOS-011 §3.4): "Your membership expired on <date>. Access is
/// read-only until <grace_end_date>." Hosted at the top of the dashboard —
/// no full-screen gate for grace.
class GraceBanner extends StatelessWidget {
  const GraceBanner({super.key, required this.entitlement});

  final Entitlement entitlement;

  static String formatDate(DateTime? date) {
    if (date == null) return '—';
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    return '${date.day} ${months[date.month - 1]} ${date.year}';
  }

  @override
  Widget build(BuildContext context) {
    final expiredOn = formatDate(entitlement.endDate);
    final readOnlyUntil = formatDate(entitlement.graceEndDate);

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF7E0),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFF2C94C)),
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline_rounded, color: Color(0xFF9A6A00), size: 22),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Your membership expired on $expiredOn. '
              'Access is read-only until $readOnlyUntil — renew at the front desk to continue.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: const Color(0xFF6B4E00),
                    height: 1.4,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Snackbar helper for blocked writes during grace (FBOS-011 §3.4 — the
/// snackbar points at the banner).
void showReadOnlySnack(BuildContext context) {
  ScaffoldMessenger.of(context).showSnackBar(
    const SnackBar(
      content: Text(
        'Read-only mode — renew your membership to continue. See the notice at the top.',
      ),
      backgroundColor: AppTheme.textPrimary,
    ),
  );
}
