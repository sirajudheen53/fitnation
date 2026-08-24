import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/async_view.dart';
import '../../../auth/presentation/providers/auth_notifier.dart';
import '../../data/models/customer_profile.dart';
import '../providers/profile_provider.dart';

/// Shows the customer's profile and health information.
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);
    final user = authState.user;
    final profileAsync = ref.watch(customerProfileProvider);
    final healthAsync = ref.watch(healthProfileProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        actions: [
          IconButton(
            icon: const Icon(Icons.card_membership_outlined),
            onPressed: () => context.push('/profile/membership'),
            tooltip: 'Membership',
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Avatar + name
          Center(
            child: CircleAvatar(
              radius: 48,
              backgroundColor: AppTheme.primary.withValues(alpha: 0.1),
              child: Text(
                (user?.fullName.isNotEmpty ?? false)
                    ? user!.fullName.substring(0, 1).toUpperCase()
                    : '?',
                style: const TextStyle(
                  fontSize: 36,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.primary,
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Center(
            child: Text(
              user?.fullName ?? 'Customer',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600),
            ),
          ),
          if (user?.email != null)
            Center(
              child: Text(
                user!.email!,
                style: const TextStyle(color: AppTheme.textSecondary),
              ),
            ),
          const SizedBox(height: 24),

          // Profile details
          AsyncView<CustomerProfile?>(
            value: profileAsync,
            onRetry: () => ref.invalidate(customerProfileProvider),
            builder: (profile) {
              if (profile == null) {
                return const EmptyState(
                  icon: Icons.person_outline,
                  title: 'Profile not found',
                );
              }
              return _ProfileDetails(profile: profile);
            },
          ),
          const SizedBox(height: 24),

          // Health info
          Text(
            'Health Information',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 12),
          AsyncView<HealthProfile?>(
            value: healthAsync,
            onRetry: () => ref.invalidate(healthProfileProvider),
            builder: (health) {
              if (health == null) {
                return const AppCard(
                  child: Text(
                    'No health profile on file.',
                    style: TextStyle(color: AppTheme.textSecondary),
                  ),
                );
              }
              return _HealthInfo(health: health);
            },
          ),
          const SizedBox(height: 32),

          // Logout
          OutlinedButton(
            onPressed: () => _logout(context, ref),
            style: OutlinedButton.styleFrom(foregroundColor: AppTheme.error),
            child: const Text('Logout'),
          ),
        ],
      ),
    );
  }

  Future<void> _logout(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Logout'),
        content: const Text('Are you sure you want to log out?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Logout', style: TextStyle(color: AppTheme.error)),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      await ref.read(authProvider.notifier).logout();
    }
  }
}

class _ProfileDetails extends StatelessWidget {
  final CustomerProfile profile;

  const _ProfileDetails({required this.profile});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        children: [
          _InfoRow(label: 'Phone', value: profile.phone ?? '—'),
          _InfoRow(label: 'Gender', value: profile.gender ?? '—'),
          _InfoRow(
            label: 'Date of Birth',
            value: profile.dateOfBirth != null
                ? '${profile.dateOfBirth!.day}/${profile.dateOfBirth!.month}/${profile.dateOfBirth!.year}'
                : '—',
          ),
          _InfoRow(label: 'Address', value: profile.address ?? '—'),
          _InfoRow(label: 'Emergency Contact', value: profile.emergencyContact ?? '—'),
          _InfoRow(label: 'Emergency Phone', value: profile.emergencyPhone ?? '—'),
        ],
      ),
    );
  }
}

class _HealthInfo extends StatelessWidget {
  final HealthProfile health;

  const _HealthInfo({required this.health});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        children: [
          _InfoRow(
            label: 'Height',
            value: health.height != null ? '${health.height!.toStringAsFixed(1)} cm' : '—',
          ),
          _InfoRow(
            label: 'Weight',
            value: health.weight != null ? '${health.weight!.toStringAsFixed(1)} kg' : '—',
          ),
          _InfoRow(label: 'Blood Group', value: health.bloodGroup ?? '—'),
          _InfoRow(label: 'Activity Level', value: health.activityLevel ?? '—'),
          _InfoRow(label: 'Medical Conditions', value: health.medicalConditions ?? '—'),
          _InfoRow(label: 'Allergies', value: health.allergies ?? '—'),
          _InfoRow(label: 'Medications', value: health.medications ?? '—'),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 14)),
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.right,
              style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 14),
            ),
          ),
        ],
      ),
    );
  }
}
