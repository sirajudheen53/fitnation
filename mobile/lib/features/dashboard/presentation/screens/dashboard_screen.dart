import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/async_view.dart';
import '../../../attendance/data/models/attendance_record.dart';
import '../../../attendance/presentation/providers/attendance_provider.dart';
import '../../../auth/presentation/providers/auth_notifier.dart';
import '../../../diet/data/models/diet_plan.dart';
import '../../../diet/presentation/providers/diet_provider.dart';
import '../../../progress/data/models/body_measurement.dart';
import '../../../progress/presentation/providers/progress_provider.dart';
import '../../../workouts/data/models/workout_plan.dart';
import '../../../workouts/presentation/providers/workout_provider.dart';

/// Customer dashboard — main screen after login.
/// Shows today's workout/diet summary, attendance streak, progress, and
/// quick actions, with a bottom navigation bar.
class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    final tabs = _buildTabs();

    return Scaffold(
      appBar: AppBar(
        title: Text(tabs[_currentIndex].title),
        actions: [
          IconButton(
            icon: const Icon(Icons.feedback_outlined),
            onPressed: () => context.push('/feedback'),
            tooltip: 'Feedback',
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

  List<_DashboardTab> _buildTabs() {
    return [
      _DashboardTab(
        title: 'Home',
        label: 'Home',
        icon: Icons.home_outlined,
        selectedIcon: Icons.home,
        body: const _HomeTab(),
      ),
      _DashboardTab(
        title: 'Workouts',
        label: 'Workouts',
        icon: Icons.fitness_center_outlined,
        selectedIcon: Icons.fitness_center,
        body: const _WorkoutsTab(),
      ),
      _DashboardTab(
        title: 'Diet',
        label: 'Diet',
        icon: Icons.restaurant_outlined,
        selectedIcon: Icons.restaurant,
        body: const _DietTab(),
      ),
      _DashboardTab(
        title: 'Progress',
        label: 'Progress',
        icon: Icons.trending_up_outlined,
        selectedIcon: Icons.trending_up,
        body: const _ProgressTab(),
      ),
      _DashboardTab(
        title: 'Profile',
        label: 'Profile',
        icon: Icons.person_outline,
        selectedIcon: Icons.person,
        body: const _ProfileTab(),
      ),
    ];
  }
}

/// Home tab with today's summary and quick actions.
class _HomeTab extends ConsumerWidget {
  const _HomeTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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

        // Quick actions
        Text(
          'Quick Actions',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: _QuickAction(
                icon: Icons.qr_code_scanner,
                label: 'Check In',
                onTap: () => context.push('/attendance/checkin'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _QuickAction(
                icon: Icons.fitness_center,
                label: 'Log Workout',
                onTap: () => context.push('/workouts'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _QuickAction(
                icon: Icons.restaurant,
                label: 'View Diet',
                onTap: () => context.push('/diet'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 24),

        // Today's workout summary
        const _TodayWorkoutCard(),
        const SizedBox(height: 16),

        // Today's diet summary
        const _TodayDietCard(),
        const SizedBox(height: 16),

        // Attendance streak + progress
        const _StatsRow(),
      ],
    );
  }
}

class _QuickAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _QuickAction({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 8),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppTheme.divider),
        ),
        child: Column(
          children: [
            Icon(icon, color: AppTheme.primary, size: 28),
            const SizedBox(height: 8),
            Text(
              label,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
            ),
          ],
        ),
      ),
    );
  }
}

/// Today's workout summary card.
class _TodayWorkoutCard extends ConsumerWidget {
  const _TodayWorkoutCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final assignmentAsync = ref.watch(activeWorkoutAssignmentProvider);

    return AsyncView<WorkoutAssignment?>(
      value: assignmentAsync,
      builder: (assignment) {
        if (assignment == null) {
          return const AppCard(
            child: Row(
              children: [
                Icon(Icons.fitness_center, color: AppTheme.primary),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'No active workout plan',
                    style: TextStyle(color: AppTheme.textSecondary),
                  ),
                ),
              ],
            ),
          );
        }

        final planAsync = ref.watch(workoutPlanProvider(assignment.planId));
        return AsyncView<WorkoutPlan>(
          value: planAsync,
          builder: (plan) {
            final today = _todayDay(plan);
            return AppCard(
              onTap: () => context.push('/workouts'),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.fitness_center, color: AppTheme.primary),
                      const SizedBox(width: 8),
                      Text(
                        'Today\'s Workout',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  if (today != null) ...[
                    Text(
                      today.name,
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${today.exercises.length} exercises',
                      style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                    ),
                  ] else
                    const Text(
                      'Rest day — no workout scheduled today.',
                      style: TextStyle(color: AppTheme.textSecondary),
                    ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  /// Picks the workout day for today based on the day of the week.
  WorkoutDay? _todayDay(WorkoutPlan plan) {
    if (plan.days.isEmpty) return null;
    final dayOfWeek = DateTime.now().weekday; // 1=Mon ... 7=Sun
    // Map to day_number (1-based), cycling through available days.
    final index = (dayOfWeek - 1) % plan.days.length;
    return plan.days[index];
  }
}

/// Today's diet summary card.
class _TodayDietCard extends ConsumerWidget {
  const _TodayDietCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final assignmentAsync = ref.watch(activeDietAssignmentProvider);

    return AsyncView<DietAssignment?>(
      value: assignmentAsync,
      builder: (assignment) {
        if (assignment == null) {
          return const AppCard(
            child: Row(
              children: [
                Icon(Icons.restaurant, color: AppTheme.primary),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'No active diet plan',
                    style: TextStyle(color: AppTheme.textSecondary),
                  ),
                ),
              ],
            ),
          );
        }

        final planAsync = ref.watch(dietPlanProvider(assignment.planId));
        return AsyncView<DietPlan>(
          value: planAsync,
          builder: (plan) {
            final today = _todayDay(plan);
            return AppCard(
              onTap: () => context.push('/diet'),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.restaurant, color: AppTheme.primary),
                      const SizedBox(width: 8),
                      Text(
                        'Today\'s Diet',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  if (today != null) ...[
                    Text(
                      today.name,
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${today.meals.length} meals · ${today.totalCalories.round()} kcal',
                      style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                    ),
                  ] else
                    const Text(
                      'No meals scheduled for today.',
                      style: TextStyle(color: AppTheme.textSecondary),
                    ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  DietDay? _todayDay(DietPlan plan) {
    if (plan.days.isEmpty) return null;
    final dayOfWeek = DateTime.now().weekday;
    final index = (dayOfWeek - 1) % plan.days.length;
    return plan.days[index];
  }
}

/// Attendance streak + progress summary row.
class _StatsRow extends ConsumerWidget {
  const _StatsRow();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final attendanceAsync = ref.watch(attendanceHistoryProvider);
    final measurementsAsync = ref.watch(bodyMeasurementsProvider);

    return Row(
      children: [
        Expanded(
          child: AsyncView<List<AttendanceRecord>>(
            value: attendanceAsync,
            builder: (records) {
              final streak = _calculateStreak(records);
              return StatCard(
                icon: Icons.local_fire_department,
                label: 'Day Streak',
                value: '$streak',
              );
            },
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: AsyncView<List<BodyMeasurement>>(
            value: measurementsAsync,
            builder: (measurements) {
              final latest = measurements.isNotEmpty ? measurements.first : null;
              final weight = latest?.weight;
              final bmi = latest?.bmi;
              return StatCard(
                icon: Icons.monitor_weight_outlined,
                label: 'Weight / BMI',
                value: weight != null
                    ? '${weight.toStringAsFixed(1)} / ${bmi?.toStringAsFixed(1) ?? '—'}'
                    : '—',
              );
            },
          ),
        ),
      ],
    );
  }

  int _calculateStreak(List<AttendanceRecord> records) {
    final days = records
        .map((r) => r.checkInTime)
        .whereType<DateTime>()
        .map((d) => DateTime(d.year, d.month, d.day))
        .toSet()
        .toList()
      ..sort((a, b) => b.compareTo(a));

    if (days.isEmpty) return 0;

    var streak = 1;
    var expected = days.first.subtract(const Duration(days: 1));

    for (final day in days.skip(1)) {
      if (day == expected) {
        streak++;
        expected = expected.subtract(const Duration(days: 1));
      } else {
        break;
      }
    }

    return streak;
  }
}

/// Workouts tab — embeds the workout list screen.
class _WorkoutsTab extends ConsumerWidget {
  const _WorkoutsTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return const _WorkoutListEmbed();
  }
}

class _WorkoutListEmbed extends ConsumerWidget {
  const _WorkoutListEmbed();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final assignmentAsync = ref.watch(activeWorkoutAssignmentProvider);

    return AsyncView<WorkoutAssignment?>(
      value: assignmentAsync,
      onRetry: () => ref.invalidate(activeWorkoutAssignmentProvider),
      builder: (assignment) {
        if (assignment == null) {
          return const EmptyState(
            icon: Icons.fitness_center,
            title: 'No active workout plan',
            subtitle: 'Your trainer hasn\'t assigned a workout plan yet.',
          );
        }
        final planAsync = ref.watch(workoutPlanProvider(assignment.planId));
        return AsyncView<WorkoutPlan>(
          value: planAsync,
          onRetry: () => ref.invalidate(workoutPlanProvider(assignment.planId)),
          builder: (plan) => ListView(
            padding: const EdgeInsets.all(16),
            children: [
              for (final day in plan.days)
                AppCard(
                  margin: const EdgeInsets.only(bottom: 12),
                  onTap: () => context.push(
                    '/workouts/detail',
                    extra: {'plan': plan, 'day': day},
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          color: AppTheme.primary.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Center(
                          child: Text(
                            '${day.dayNumber ?? '•'}',
                            style: const TextStyle(
                              color: AppTheme.primary,
                              fontSize: 18,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              day.name,
                              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${day.exercises.length} exercises',
                              style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                            ),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right, color: AppTheme.textSecondary),
                    ],
                  ),
                ),
            ],
          ),
        );
      },
    );
  }
}

/// Diet tab — embeds the diet plan screen.
class _DietTab extends ConsumerWidget {
  const _DietTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final assignmentAsync = ref.watch(activeDietAssignmentProvider);

    return AsyncView<DietAssignment?>(
      value: assignmentAsync,
      onRetry: () => ref.invalidate(activeDietAssignmentProvider),
      builder: (assignment) {
        if (assignment == null) {
          return const EmptyState(
            icon: Icons.restaurant,
            title: 'No active diet plan',
            subtitle: 'Your trainer hasn\'t assigned a diet plan yet.',
          );
        }
        final planAsync = ref.watch(dietPlanProvider(assignment.planId));
        return AsyncView<DietPlan>(
          value: planAsync,
          onRetry: () => ref.invalidate(dietPlanProvider(assignment.planId)),
          builder: (plan) => ListView(
            padding: const EdgeInsets.all(16),
            children: [
              for (final day in plan.days)
                AppCard(
                  margin: const EdgeInsets.only(bottom: 12),
                  onTap: () => context.push(
                    '/diet/meals',
                    extra: {'plan': plan, 'day': day},
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          color: AppTheme.primary.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Center(
                          child: Text(
                            '${day.dayNumber ?? '•'}',
                            style: const TextStyle(
                              color: AppTheme.primary,
                              fontSize: 18,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              day.name,
                              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${day.meals.length} meals · ${day.totalCalories.round()} kcal',
                              style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                            ),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right, color: AppTheme.textSecondary),
                    ],
                  ),
                ),
            ],
          ),
        );
      },
    );
  }
}

/// Progress tab — embeds the progress screen.
class _ProgressTab extends ConsumerWidget {
  const _ProgressTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final measurementsAsync = ref.watch(bodyMeasurementsProvider);

    return AsyncView<List<BodyMeasurement>>(
      value: measurementsAsync,
      onRetry: () => ref.invalidate(bodyMeasurementsProvider),
      builder: (measurements) {
        if (measurements.isEmpty) {
          return const EmptyState(
            icon: Icons.monitor_weight_outlined,
            title: 'No measurements yet',
            subtitle: 'Your measurements will appear here once recorded.',
          );
        }
        final latest = measurements.first;
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Latest Measurements',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      _Metric(label: 'Weight', value: latest.weight != null ? '${latest.weight!.toStringAsFixed(1)} kg' : '—'),
                      _Metric(label: 'BMI', value: latest.bmi != null ? latest.bmi!.toStringAsFixed(1) : '—'),
                      _Metric(label: 'Body Fat', value: latest.bodyFat != null ? '${latest.bodyFat!.toStringAsFixed(1)}%' : '—'),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: () => context.push('/progress/photos'),
              icon: const Icon(Icons.photo_library_outlined),
              label: const Text('View Progress Photos'),
            ),
          ],
        );
      },
    );
  }
}

class _Metric extends StatelessWidget {
  final String label;
  final String value;

  const _Metric({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: AppTheme.primary),
        ),
        const SizedBox(height: 4),
        Text(label, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
      ],
    );
  }
}

/// Profile tab — embeds the profile screen.
class _ProfileTab extends ConsumerWidget {
  const _ProfileTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);
    final user = authState.user;

    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
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
          Center(child: Text(user!.email!, style: const TextStyle(color: AppTheme.textSecondary))),
        const SizedBox(height: 24),
        AppCard(
          child: Column(
            children: [
              _InfoRow(label: 'Role', value: user?.role.toUpperCase() ?? '—'),
              _InfoRow(label: 'Gym', value: user?.tenantName ?? '—'),
              if (user?.branchName != null) _InfoRow(label: 'Branch', value: user!.branchName!),
            ],
          ),
        ),
        const SizedBox(height: 16),
        OutlinedButton.icon(
          onPressed: () => context.push('/profile/membership'),
          icon: const Icon(Icons.card_membership_outlined),
          label: const Text('View Membership'),
        ),
        const SizedBox(height: 16),
        OutlinedButton(
          onPressed: () => _logout(context, ref),
          style: OutlinedButton.styleFrom(foregroundColor: AppTheme.error),
          child: const Text('Logout'),
        ),
      ],
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
