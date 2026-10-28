import 'package:flutter/material.dart';

import '../../../../core/theme/app_theme.dart';
import '../providers/plan_assignment_providers.dart';

/// Shared view for the workout/diet assignment tabs (issue #94).
///
/// Renders the four states — loading, error+retry, empty, and the list — for
/// whichever typed assignment list the screen feeds in.
class PlanAssignmentsView<T> extends StatelessWidget {
  final PlanAssignmentsState<T> state;
  final Future<void> Function() onRefresh;
  final String emptyTitle;
  final String emptySubtitle;
  final Widget Function(BuildContext context, T assignment) itemBuilder;

  const PlanAssignmentsView({
    super.key,
    required this.state,
    required this.onRefresh,
    required this.emptyTitle,
    required this.emptySubtitle,
    required this.itemBuilder,
  });

  @override
  Widget build(BuildContext context) {
    // Keep any previously loaded list visible while a refresh is in flight;
    // only show the blocking spinner when there is nothing to show yet.
    final showLoading =
        state.status == PlanAssignmentsStatus.loading && state.assignments.isEmpty;
    final showError = state.status == PlanAssignmentsStatus.error &&
        state.assignments.isEmpty;

    if (showLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (showError) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.cloud_off_outlined,
                  size: 48, color: AppTheme.textSecondary),
              const SizedBox(height: 16),
              Text(
                state.errorMessage ?? 'Something went wrong.',
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 16),
              OutlinedButton(
                onPressed: onRefresh,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (state.assignments.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.inbox_outlined, size: 48, color: AppTheme.textSecondary),
            const SizedBox(height: 16),
            Text(emptyTitle, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(
              emptySubtitle,
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppTheme.textSecondary),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: onRefresh,
      child: ListView.separated(
        padding: const EdgeInsets.all(24),
        itemCount: state.assignments.length,
        separatorBuilder: (_, _) => const SizedBox(height: 12),
        itemBuilder: (context, index) =>
            itemBuilder(context, state.assignments[index]),
      ),
    );
  }
}
