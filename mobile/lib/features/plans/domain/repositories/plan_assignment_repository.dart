import '../../../../core/errors/failures.dart';
import '../../data/data_sources/plan_assignment_remote_data_source.dart';
import '../../data/models/diet_assignment_model.dart';
import '../../data/models/workout_assignment_model.dart';

/// Repository for the logged-in customer's plan assignments (issue #94).
class PlanAssignmentRepository {
  final PlanAssignmentRemoteDataSource _remote;

  PlanAssignmentRepository(this._remote);

  /// Active workout assignments for the logged-in customer.
  Future<({List<WorkoutAssignmentModel>? assignments, Failure? error})>
      activeWorkoutAssignments() async {
    try {
      final assignments = await _remote.fetchActiveWorkoutAssignments();
      return (assignments: assignments, error: null);
    } on Failure catch (e) {
      return (assignments: null, error: e);
    } catch (e) {
      return (assignments: null, error: UnknownFailure(message: e.toString()));
    }
  }

  /// Active diet (meal plan) assignments for the logged-in customer.
  Future<({List<DietAssignmentModel>? assignments, Failure? error})>
      activeDietAssignments() async {
    try {
      final assignments = await _remote.fetchActiveDietAssignments();
      return (assignments: assignments, error: null);
    } on Failure catch (e) {
      return (assignments: null, error: e);
    } catch (e) {
      return (assignments: null, error: UnknownFailure(message: e.toString()));
    }
  }
}
