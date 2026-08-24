import '../../../../core/errors/failures.dart';
import '../data/data_sources/diet_remote_data_source.dart';
import '../data/models/diet_plan.dart';

/// Repository for diet-related operations.
class DietRepository {
  final DietRemoteDataSource _remote;

  DietRepository(this._remote);

  /// Fetches the active diet assignment for a customer.
  Future<({DietAssignment? assignment, Failure? error})> getActiveAssignment(
    int customerId,
  ) async {
    try {
      final assignment = await _remote.getActiveAssignment(customerId);
      return (assignment: assignment, error: null);
    } on Failure catch (e) {
      return (assignment: null, error: e);
    } catch (e) {
      return (assignment: null, error: UnknownFailure(message: e.toString()));
    }
  }

  /// Fetches a diet plan by id.
  Future<({DietPlan? plan, Failure? error})> getDietPlan(int planId) async {
    try {
      final plan = await _remote.getDietPlan(planId);
      return (plan: plan, error: null);
    } on Failure catch (e) {
      return (plan: null, error: e);
    } catch (e) {
      return (plan: null, error: UnknownFailure(message: e.toString()));
    }
  }
}
