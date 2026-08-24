import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/async_view.dart';
import '../../data/models/workout_plan.dart';
import '../providers/workout_provider.dart';

/// Shows the customer's assigned workout plan.
class WorkoutListScreen extends ConsumerWidget {
  const WorkoutListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final assignmentAsync = ref.watch(activeWorkoutAssignmentProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Workouts')),
      body: AsyncView<WorkoutAssignment?>(
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
            builder: (plan) => _PlanView(plan: plan),
          );
        },
      ),
    );
  }
}

class _PlanView extends StatelessWidget {
  final WorkoutPlan plan;

  const _PlanView({required this.plan});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Plan header card
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
                plan.name,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                ),
              ),
              if (plan.description != null) ...[
                const SizedBox(height: 8),
                Text(
                  plan.description!,
                  style: TextStyle(color: Colors.white.withValues(alpha: 0.85)),
                ),
              ],
              const SizedBox(height: 16),
              Row(
                children: [
                  _PlanMeta(icon: Icons.calendar_today, label: '${plan.durationWeeks ?? '—'} weeks'),
                  const SizedBox(width: 16),
                  _PlanMeta(icon: Icons.repeat, label: '${plan.sessionsPerWeek ?? '—'}/week'),
                  if (plan.difficulty != null) ...[
                    const SizedBox(width: 16),
                    _PlanMeta(icon: Icons.speed, label: plan.difficulty!),
                  ],
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),

        Text(
          'Workout Days',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 12),

        if (plan.days.isEmpty)
          const EmptyState(
            icon: Icons.event_note,
            title: 'No days in this plan',
          )
        else
          for (final day in plan.days) ...[
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
                        if (day.description != null) ...[
                          const SizedBox(height: 4),
                          Text(
                            day.description!,
                            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                          ),
                        ],
                        const SizedBox(height: 4),
                        Text(
                          '${day.exercises.length} exercises',
                          style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                  const Icon(Icons.chevron_right, color: AppTheme.textSecondary),
                ],
              ),
            ),
          ],
      ],
    );
  }
}

class _PlanMeta extends StatelessWidget {
  final IconData icon;
  final String label;

  const _PlanMeta({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, color: Colors.white, size: 16),
        const SizedBox(width: 6),
        Text(
          label,
          style: TextStyle(color: Colors.white.withValues(alpha: 0.9), fontSize: 13),
        ),
      ],
    );
  }
}
