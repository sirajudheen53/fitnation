import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/async_view.dart';
import '../../data/models/customer_profile.dart';
import '../providers/profile_provider.dart';

/// Shows the customer's membership status.
class MembershipScreen extends ConsumerWidget {
  const MembershipScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final membershipsAsync = ref.watch(membershipsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Membership')),
      body: AsyncView<List<Membership>>(
        value: membershipsAsync,
        onRetry: () => ref.invalidate(membershipsProvider),
        builder: (memberships) {
          if (memberships.isEmpty) {
            return const EmptyState(
              icon: Icons.card_membership,
              title: 'No membership found',
              subtitle: 'Contact the gym to set up your membership.',
            );
          }

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              for (final membership in memberships)
                _MembershipCard(membership: membership),
            ],
          );
        },
      ),
    );
  }
}

class _MembershipCard extends StatelessWidget {
  final Membership membership;

  const _MembershipCard({required this.membership});

  @override
  Widget build(BuildContext context) {
    final isActive = membership.isActive;

    return AppCard(
      margin: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: (isActive ? AppTheme.accent : AppTheme.textSecondary)
                      .withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  isActive ? Icons.verified : Icons.card_membership,
                  color: isActive ? AppTheme.accent : AppTheme.textSecondary,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      membership.planName ?? 'Membership',
                      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                    ),
                    if (membership.branchName != null)
                      Text(
                        membership.branchName!,
                        style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                      ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: (isActive ? AppTheme.accent : AppTheme.error).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  isActive ? 'Active' : 'Inactive',
                  style: TextStyle(
                    color: isActive ? AppTheme.accent : AppTheme.error,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          const Divider(height: 1),
          const SizedBox(height: 12),
          _InfoRow(label: 'Status', value: membership.status ?? '—'),
          _InfoRow(
            label: 'Start Date',
            value: _formatDate(membership.startDate),
          ),
          _InfoRow(
            label: 'End Date',
            value: _formatDate(membership.endDate),
          ),
          if (membership.price != null)
            _InfoRow(
              label: 'Price',
              value: '₹${membership.price!.toStringAsFixed(0)}',
            ),
        ],
      ),
    );
  }

  String _formatDate(DateTime? date) {
    if (date == null) return '—';
    return '${date.day}/${date.month}/${date.year}';
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 14)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 14)),
        ],
      ),
    );
  }
}
