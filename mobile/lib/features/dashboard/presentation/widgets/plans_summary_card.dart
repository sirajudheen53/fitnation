import 'package:flutter/material.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../plans/data/models/diet_assignment_model.dart';
import '../../../plans/data/models/workout_assignment_model.dart';
import '../../../plans/presentation/providers/plan_assignment_providers.dart';

/// Home card summarizing the member's assigned plans (issue #95).
///
/// Rows deep-link into the Workouts / Diet tabs, so the card stays a
/// summary — the full lists live on their tabs. Rows are only rendered for
/// tabs the member actually has (the dashboard passes null callbacks
/// otherwise), and the whole card disappears when neither tab exists.
class PlansSummaryCard extends StatelessWidget {
  final PlanAssignmentsState<WorkoutAssignmentModel> workouts;
  final PlanAssignmentsState<DietAssignmentModel> diet;
  final VoidCallback? onOpenWorkouts;
  final VoidCallback? onOpenDiet;

  const PlansSummaryCard({
    super.key,
    required this.workouts,
    required this.diet,
    this.onOpenWorkouts,
    this.onOpenDiet,
  });

  @override
  Widget build(BuildContext context) {
    if (onOpenWorkouts == null && onOpenDiet == null) {
      return const SizedBox.shrink();
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              'Your plans',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
            ),
          ),
          if (onOpenWorkouts != null)
            _PlanRow(
              icon: Icons.fitness_center_outlined,
              label: 'Workout plans',
              detail: _detail(
                status: workouts.status,
                count: workouts.assignments.length,
                firstName: workouts.assignments.isEmpty
                    ? null
                    : workouts.assignments.first.workoutPlanName,
              ),
              onTap: onOpenWorkouts,
            ),
          if (onOpenDiet != null)
            _PlanRow(
              icon: Icons.restaurant_outlined,
              label: 'Meal plans',
              detail: _detail(
                status: diet.status,
                count: diet.assignments.length,
                firstName:
                    diet.assignments.isEmpty ? null : diet.assignments.first.dietPlanName,
              ),
              onTap: onOpenDiet,
            ),
        ],
      ),
    );
  }

  String _detail({
    required PlanAssignmentsStatus status,
    required int count,
    String? firstName,
  }) {
    switch (status) {
      case PlanAssignmentsStatus.idle:
      case PlanAssignmentsStatus.loading:
        return 'Loading…';
      case PlanAssignmentsStatus.error:
        return 'Couldn\'t load';
      case PlanAssignmentsStatus.loaded:
        if (count == 0) return 'None assigned';
        if (count == 1) return firstName!;
        return '$firstName +${count - 1} more';
    }
  }
}

class _PlanRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String detail;
  final VoidCallback? onTap;

  const _PlanRow({
    required this.icon,
    required this.label,
    required this.detail,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: AppTheme.primary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: AppTheme.primary, size: 22),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                label,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                ),
              ),
            ),
            Text(
              detail,
              style: const TextStyle(
                  fontSize: 13, color: AppTheme.textSecondary),
            ),
            const SizedBox(width: 4),
            const Icon(Icons.chevron_right,
                size: 20, color: AppTheme.textSecondary),
          ],
        ),
      ),
    );
  }
}
