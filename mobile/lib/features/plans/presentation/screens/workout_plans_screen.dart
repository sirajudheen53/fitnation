import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/workout_assignment_model.dart';
import '../providers/plan_assignment_providers.dart';
import '../widgets/plan_assignment_card.dart';
import '../widgets/plan_assignments_view.dart';

/// Workouts tab — shows the workout plans assigned to the customer (#94).
class WorkoutPlansScreen extends ConsumerStatefulWidget {
  const WorkoutPlansScreen({super.key});

  @override
  ConsumerState<WorkoutPlansScreen> createState() => _WorkoutPlansScreenState();
}

class _WorkoutPlansScreenState extends ConsumerState<WorkoutPlansScreen> {
  @override
  void initState() {
    super.initState();
    // Deferred: load() writes state synchronously, which Riverpod forbids
    // during the build phase.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) ref.read(workoutAssignmentsProvider.notifier).load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(workoutAssignmentsProvider);

    return PlanAssignmentsView<WorkoutAssignmentModel>(
      state: state,
      onRefresh: () => ref.read(workoutAssignmentsProvider.notifier).load(),
      emptyTitle: 'No workout plan yet',
      emptySubtitle: 'Your trainer hasn\'t assigned you a workout plan. '
          'Check back once they do!',
      itemBuilder: (context, assignment) => PlanAssignmentCard(
        key: ValueKey(assignment.id),
        planName: assignment.workoutPlanName,
        isActive: assignment.isActive,
        startDate: assignment.startDate,
        endDate: assignment.endDate,
        notes: assignment.notes,
      ),
    );
  }
}
