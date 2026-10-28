import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/diet_assignment_model.dart';
import '../providers/plan_assignment_providers.dart';
import '../widgets/plan_assignment_card.dart';
import '../widgets/plan_assignments_view.dart';

/// Diet tab — shows the meal plans assigned to the customer (#94).
class DietPlansScreen extends ConsumerStatefulWidget {
  const DietPlansScreen({super.key});

  @override
  ConsumerState<DietPlansScreen> createState() => _DietPlansScreenState();
}

class _DietPlansScreenState extends ConsumerState<DietPlansScreen> {
  @override
  void initState() {
    super.initState();
    // Deferred: load() writes state synchronously, which Riverpod forbids
    // during the build phase.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) ref.read(dietAssignmentsProvider.notifier).load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(dietAssignmentsProvider);

    return PlanAssignmentsView<DietAssignmentModel>(
      state: state,
      onRefresh: () => ref.read(dietAssignmentsProvider.notifier).load(),
      emptyTitle: 'No meal plan yet',
      emptySubtitle:
          'Your trainer hasn\'t assigned you a meal plan. Check back once they do!',
      itemBuilder: (context, assignment) => PlanAssignmentCard(
        key: ValueKey(assignment.id),
        planName: assignment.dietPlanName,
        isActive: assignment.isActive,
        startDate: assignment.startDate,
        endDate: assignment.endDate,
        notes: assignment.notes,
      ),
    );
  }
}
