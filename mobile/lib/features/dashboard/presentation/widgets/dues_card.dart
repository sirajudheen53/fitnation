import 'package:flutter/material.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/utils/currency_formatter.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../memberships/data/models/membership_model.dart';
import '../../../memberships/presentation/providers/membership_providers.dart';
import '../../../payments/data/models/payment_model.dart';
import '../../../payments/presentation/providers/payment_providers.dart';

/// Home card showing the current membership and any pending dues (issue #95).
///
/// In-app payment isn't possible for customers yet (order creation is a
/// staff endpoint), so the card states the dues and points to the gym's
/// payment-link flow instead of a dead "Pay" button. Deliberately keeps
/// working when the entitlement has expired — that's the state it explains.
class DuesCard extends StatelessWidget {
  final MembershipState membership;
  final PendingPaymentsState dues;
  final Future<void> Function() onRetry;

  const DuesCard({
    super.key,
    required this.membership,
    required this.dues,
    required this.onRetry,
  });

  bool get _hasMembership => membership.membership != null;
  bool get _hasDues => dues.payments.isNotEmpty;

  @override
  Widget build(BuildContext context) {
    if (!_hasMembership && !_hasDues) {
      return _frame(_buildFallback());
    }

    final children = <Widget>[];

    final membershipModel = membership.membership;
    if (membershipModel != null) {
      children.add(_MembershipRow(
        icon: membershipModel.isActive
            ? Icons.card_membership
            : Icons.card_membership_outlined,
        iconColor:
            membershipModel.isActive ? AppTheme.primary : AppTheme.textSecondary,
        title: membershipModel.planName,
        subtitle: _membershipSubtitle(membershipModel),
      ));
    }

    if (_hasDues) {
      if (children.isNotEmpty) children.add(const SizedBox(height: 12));
      children.add(_DuesSummary(payments: dues.payments));
    } else if (dues.status == PendingPaymentsStatus.loaded &&
        membershipModel != null) {
      children.add(const SizedBox(height: 8));
      children.add(const _AllCleared());
    }

    return _frame(
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    );
  }

  Widget _buildFallback() {
    if (membership.status == MembershipStatus.loading ||
        dues.status == PendingPaymentsStatus.loading) {
      return const Row(
        children: [
          SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          SizedBox(width: 12),
          Expanded(
            child: Text(
              'Loading your membership…',
              style: TextStyle(color: AppTheme.textSecondary, fontSize: 14),
            ),
          ),
        ],
      );
    }

    if (membership.status == MembershipStatus.error &&
        dues.status == PendingPaymentsStatus.error) {
      return Row(
        children: [
          const Icon(Icons.cloud_off_outlined,
              size: 20, color: AppTheme.textSecondary),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              membership.errorMessage ??
                  dues.errorMessage ??
                  'Couldn\'t load your membership.',
              style:
                  const TextStyle(color: AppTheme.textSecondary, fontSize: 14),
            ),
          ),
          TextButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      );
    }

    return const _MembershipRow(
      icon: Icons.card_membership_outlined,
      iconColor: AppTheme.textSecondary,
      title: 'No membership yet',
      subtitle: 'Ask your gym to set you up.',
    );
  }

  String _membershipSubtitle(MembershipModel membership) {
    switch (membership.status) {
      case 'active':
        return membership.endDate == null
            ? 'Active'
            : 'Active till ${formatDateShort(membership.endDate!)}';
      case 'expired':
        return membership.endDate == null
            ? 'Expired'
            : 'Expired on ${formatDateShort(membership.endDate!)}';
      case 'cancelled':
        return 'Cancelled';
    }
    return membership.status;
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

/// The dues block: headline amount plus a one-line breakdown.
class _DuesSummary extends StatelessWidget {
  final List<PaymentModel> payments;

  const _DuesSummary({required this.payments});

  @override
  Widget build(BuildContext context) {
    final total = PaymentModel.totalAmount(payments);
    final first = payments.first;
    final what = (first.planName?.isNotEmpty ?? false)
        ? first.planName!
        : (first.kind == 'admission' ? 'Admission' : 'Membership');
    final breakdown = payments.length > 1
        ? '$what · ${payments.length} pending payments'
        : '$what · pending';

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.error.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const Icon(Icons.receipt_long_outlined,
              size: 20, color: AppTheme.error),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${formatRupeeAmount(total.toString())} due',
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.error,
                  ),
                ),
                Text(
                  breakdown,
                  style: const TextStyle(
                      fontSize: 13, color: AppTheme.textSecondary),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _AllCleared extends StatelessWidget {
  const _AllCleared();

  @override
  Widget build(BuildContext context) {
    return const Row(
      children: [
        Icon(Icons.check_circle_outline, size: 16, color: Color(0xFF00996E)),
        SizedBox(width: 6),
        Text(
          'No pending dues',
          style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
        ),
      ],
    );
  }
}

class _MembershipRow extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final String subtitle;

  const _MembershipRow({
    required this.icon,
    this.iconColor = AppTheme.primary,
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
              Text(
                title,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
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
