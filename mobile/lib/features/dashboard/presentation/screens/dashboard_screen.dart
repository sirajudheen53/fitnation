import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/auth_notifier.dart';

/// Customer dashboard scaffold — main screen after login.
/// Shows bottom navigation with permission-filtered tabs.
class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);
    final user = authState.user;
    final permissions = authState.permissions;

    // Build list of allowed tabs based on permissions
    final tabs = _buildAllowedTabs(permissions);

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
      body: _buildHomeBody(),
    ));

    // Workouts tab
    if (permissions.contains('workouts.view_workout')) {
      tabs.add(_DashboardTab(
        title: 'Workouts',
        label: 'Workouts',
        icon: Icons.fitness_center_outlined,
        selectedIcon: Icons.fitness_center,
        body: _buildPlaceholder('Workouts', 'Your workout plans will appear here'),
      ));
    }

    // Diet tab
    if (permissions.contains('diets.view_diet')) {
      tabs.add(_DashboardTab(
        title: 'Diet',
        label: 'Diet',
        icon: Icons.restaurant_outlined,
        selectedIcon: Icons.restaurant,
        body: _buildPlaceholder('Diet Plans', 'Your meal plans will appear here'),
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

  Widget _buildHomeBody() {
    final authState = ref.watch(authProvider);
    final user = authState.user;

    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        // Greeting card
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [AppTheme.primary, AppTheme.primaryLight],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Welcome back,',
                style: TextStyle(color: Colors.white.withValues(alpha: 0.8), fontSize: 14),
              ),
              const SizedBox(height: 4),
              Text(
                user?.fullName ?? 'Athlete',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 24,
                  fontWeight: FontWeight.w700,
                ),
              ),
              if (user?.tenantName != null) ...[
                const SizedBox(height: 8),
                Text(
                  user!.tenantName!,
                  style: TextStyle(color: Colors.white.withValues(alpha: 0.7), fontSize: 13),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 24),

        // Quick stats placeholder
        Text(
          'Quick Stats',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 16),
        GridView.count(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisCount: 2,
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.5,
          children: [
            _buildStatCard(Icons.fitness_center, 'Workouts', '—'),
            _buildStatCard(Icons.restaurant, 'Meals', '—'),
            _buildStatCard(Icons.event_available, 'Check-ins', '—'),
            _buildStatCard(Icons.trending_up, 'Progress', '—'),
          ],
        ),
      ],
    );
  }

  Widget _buildStatCard(IconData icon, String label, String value) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Icon(icon, color: AppTheme.primary, size: 24),
          Text(label, style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
          Text(value, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
        ],
      ),
    );
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