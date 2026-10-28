import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../auth/presentation/providers/auth_notifier.dart';
import '../../../plans/presentation/screens/diet_plans_screen.dart';
import '../../../plans/presentation/screens/workout_plans_screen.dart';
import 'home_tab.dart';

/// Customer dashboard scaffold — main screen after login.
/// Shows bottom navigation with permission-filtered tabs.
class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  int _currentIndex = 0;
  late List<_DashboardTab> _tabs;

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);
    final permissions = authState.permissions;

    // Build list of allowed tabs based on permissions
    _tabs = _buildAllowedTabs(permissions);
    final tabs = _tabs;

    return Scaffold(
      appBar: AppBar(
        title: Text(tabs[_currentIndex].title),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout_outlined),
            onPressed: () => _logout(context),
          ),
        ],
      ),
      body: tabs[_currentIndex].body,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (index) => setState(() => _currentIndex = index),
        destinations: tabs
            .map((tab) => NavigationDestination(
                  icon: Icon(tab.icon),
                  selectedIcon: Icon(tab.selectedIcon),
                  label: tab.label,
                ))
            .toList(),
      ),
    );
  }

  List<_DashboardTab> _buildAllowedTabs(List<String> permissions) {
    final tabs = <_DashboardTab>[];

    // Home tab (always visible)
    tabs.add(_DashboardTab(
      title: 'Home',
      label: 'Home',
      icon: Icons.home_outlined,
      selectedIcon: Icons.home,
      body: HomeTab(
        // Deep-links into the plan tabs; null hides the row on the home card.
        onOpenWorkouts: permissions.contains('workouts.view_workout')
            ? () => _openTabByTitle('Workouts')
            : null,
        onOpenDiet: permissions.contains('diets.view_diet')
            ? () => _openTabByTitle('Diet')
            : null,
      ),
    ));

    // Workouts tab — the customer's assigned workout plans (#94)
    if (permissions.contains('workouts.view_workout')) {
      tabs.add(_DashboardTab(
        title: 'Workouts',
        label: 'Workouts',
        icon: Icons.fitness_center_outlined,
        selectedIcon: Icons.fitness_center,
        body: const WorkoutPlansScreen(),
      ));
    }

    // Diet tab — the customer's assigned meal plans (#94)
    if (permissions.contains('diets.view_diet')) {
      tabs.add(_DashboardTab(
        title: 'Diet',
        label: 'Diet',
        icon: Icons.restaurant_outlined,
        selectedIcon: Icons.restaurant,
        body: const DietPlansScreen(),
      ));
    }

    // Attendance tab
    if (permissions.contains('attendance.view_attendance')) {
      tabs.add(_DashboardTab(
        title: 'Attendance',
        label: 'Attendance',
        icon: Icons.event_available_outlined,
        selectedIcon: Icons.event_available,
        body: _buildPlaceholder('Attendance', 'Your check-in history will appear here'),
      ));
    }

    // Profile tab (always visible)
    tabs.add(_DashboardTab(
      title: 'Profile',
      label: 'Profile',
      icon: Icons.person_outline,
      selectedIcon: Icons.person,
      body: _buildProfileBody(),
    ));

    // Ensure index is in bounds
    if (_currentIndex >= tabs.length) _currentIndex = 0;

    return tabs;
  }

  /// Switches to the bottom-nav tab with the given title (issue #95).
  void _openTabByTitle(String title) {
    final index = _tabs.indexWhere((tab) => tab.title == title);
    if (index == -1) return;
    setState(() => _currentIndex = index);
  }

  Widget _buildProfileBody() {
    final authState = ref.watch(authProvider);
    final user = authState.user;
    final permissions = authState.permissions;

    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        // Avatar
        Center(
          child: CircleAvatar(
            radius: 48,
            backgroundColor: AppTheme.primary.withValues(alpha: 0.1),
            child: Text(
              (user?.fullName.isNotEmpty ?? false)
                  ? user!.fullName.substring(0, 1).toUpperCase()
                  : '?',
              style: const TextStyle(fontSize: 36, fontWeight: FontWeight.w700, color: AppTheme.primary),
            ),
          ),
        ),
        const SizedBox(height: 16),
        Center(
          child: Text(
            user?.fullName ?? 'User',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600),
          ),
        ),
        if (user?.email != null)
          Center(child: Text(user!.email!, style: TextStyle(color: AppTheme.textSecondary))),

        const SizedBox(height: 32),

        // Info section
        _buildInfoSection('Account', [
          _InfoRow('Role', user?.role.toUpperCase() ?? '—'),
          _InfoRow('Gym', user?.tenantName ?? '—'),
          if (user?.branchName != null) _InfoRow('Branch', user!.branchName!),
        ]),

        const SizedBox(height: 24),

        _buildInfoSection('Permissions', [
          for (final p in permissions) _InfoRow('•', p),
        ]),

        const SizedBox(height: 32),

        // Logout button
        OutlinedButton(
          onPressed: () => _logout(context),
          style: OutlinedButton.styleFrom(foregroundColor: AppTheme.error),
          child: const Text('Logout'),
        ),
      ],
    );
  }

  Widget _buildInfoSection(String title, List<Widget> children) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppTheme.divider),
          ),
          child: Column(children: children),
        ),
      ],
    );
  }

  Widget _buildPlaceholder(String title, String subtitle) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.construction, size: 48, color: AppTheme.textSecondary),
          const SizedBox(height: 16),
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          Text(subtitle, style: TextStyle(color: AppTheme.textSecondary)),
        ],
      ),
    );
  }

  Future<void> _logout(BuildContext context) async {
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

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: AppTheme.textSecondary, fontSize: 14)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 14)),
        ],
      ),
    );
  }
}

class _DashboardTab {
  final String title;
  final String label;
  final IconData icon;
  final IconData selectedIcon;
  final Widget body;

  _DashboardTab({
    required this.title,
    required this.label,
    required this.icon,
    required this.selectedIcon,
    required this.body,
  });
}