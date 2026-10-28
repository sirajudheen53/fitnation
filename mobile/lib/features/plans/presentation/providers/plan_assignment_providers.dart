import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/data/data_sources/api_client.dart';
import '../../data/data_sources/plan_assignment_remote_data_source.dart';
import '../../data/models/diet_assignment_model.dart';
import '../../data/models/workout_assignment_model.dart';
import '../../domain/repositories/plan_assignment_repository.dart';

/// Load lifecycle of a plan-assignment list.
enum PlanAssignmentsStatus { idle, loading, loaded, error }

/// State for one plan-assignment list (workout or diet).
@immutable
class PlanAssignmentsState<T> {
  final PlanAssignmentsStatus status;
  final List<T> assignments;

  /// Populated when [status] is [PlanAssignmentsStatus.error].
  final String? errorMessage;

  const PlanAssignmentsState({
    this.status = PlanAssignmentsStatus.idle,
    this.assignments = const [],
    this.errorMessage,
  });

  PlanAssignmentsState<T> copyWith({
    PlanAssignmentsStatus? status,
    List<T>? assignments,
    String? errorMessage,
  }) {
    return PlanAssignmentsState<T>(
      status: status ?? this.status,
      assignments: assignments ?? this.assignments,
      errorMessage: errorMessage,
    );
  }
}

/// Base for notifiers that load one plan-assignment list.
abstract class PlanAssignmentsNotifier<T>
    extends StateNotifier<PlanAssignmentsState<T>> {
  // Non-const with an explicit type argument: a bare const state would
  // reify T as Never (List<Never> assignments at runtime).
  PlanAssignmentsNotifier() : super(PlanAssignmentsState<T>());

  /// (Re)loads the assignments from the backend.
  Future<void> load();
}

/// Loads the customer's active workout assignments.
class WorkoutAssignmentsNotifier
    extends PlanAssignmentsNotifier<WorkoutAssignmentModel> {
  final PlanAssignmentRepository _repository;

  WorkoutAssignmentsNotifier(this._repository);

  @override
  Future<void> load() async {
    state = state.copyWith(
      status: PlanAssignmentsStatus.loading,
      errorMessage: null,
    );

    final result = await _repository.activeWorkoutAssignments();

    if (result.error != null) {
      state = state.copyWith(
        status: PlanAssignmentsStatus.error,
        errorMessage: result.error!.message,
      );
      return;
    }

    state = state.copyWith(
      status: PlanAssignmentsStatus.loaded,
      assignments: result.assignments ?? const [],
    );
  }
}

/// Loads the customer's active diet (meal plan) assignments.
class DietAssignmentsNotifier extends PlanAssignmentsNotifier<DietAssignmentModel> {
  final PlanAssignmentRepository _repository;

  DietAssignmentsNotifier(this._repository);

  @override
  Future<void> load() async {
    state = state.copyWith(
      status: PlanAssignmentsStatus.loading,
      errorMessage: null,
    );

    final result = await _repository.activeDietAssignments();

    if (result.error != null) {
      state = state.copyWith(
        status: PlanAssignmentsStatus.error,
        errorMessage: result.error!.message,
      );
      return;
    }

    state = state.copyWith(
      status: PlanAssignmentsStatus.loaded,
      assignments: result.assignments ?? const [],
    );
  }
}

/// Provides the plan-assignment remote data source.
final planAssignmentRemoteDataSourceProvider =
    Provider<PlanAssignmentRemoteDataSource>((ref) {
  return PlanAssignmentRemoteDataSource(ApiClient.getInstance());
});

/// Provides the plan-assignment repository.
final planAssignmentRepositoryProvider = Provider<PlanAssignmentRepository>((
  ref,
) {
  return PlanAssignmentRepository(ref.read(planAssignmentRemoteDataSourceProvider));
});

/// Provides the customer's active workout assignments.
final workoutAssignmentsProvider = StateNotifierProvider<
    WorkoutAssignmentsNotifier, PlanAssignmentsState<WorkoutAssignmentModel>>((
  ref,
) {
  return WorkoutAssignmentsNotifier(ref.read(planAssignmentRepositoryProvider));
});

/// Provides the customer's active diet (meal plan) assignments.
final dietAssignmentsProvider = StateNotifierProvider<
    DietAssignmentsNotifier, PlanAssignmentsState<DietAssignmentModel>>((ref) {
  return DietAssignmentsNotifier(ref.read(planAssignmentRepositoryProvider));
});
