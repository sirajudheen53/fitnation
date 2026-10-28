import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/plans/data/data_sources/plan_assignment_remote_data_source.dart';
import 'package:fitnation_app/features/plans/data/models/diet_assignment_model.dart';
import 'package:fitnation_app/features/plans/data/models/workout_assignment_model.dart';
import 'package:fitnation_app/features/plans/domain/repositories/plan_assignment_repository.dart';

/// Canned assignment rows shared across plan tests.
WorkoutAssignmentModel workoutAssignment({int id = 1}) => WorkoutAssignmentModel(
      id: id,
      customer: 2,
      workoutPlan: 3,
      workoutPlanName: 'Beginner Strength',
      customerName: 'Arjun Nair',
      startDate: DateTime(2026, 10, 1),
      createdAt: DateTime(2026, 10, 1),
      updatedAt: DateTime(2026, 10, 1),
    );

DietAssignmentModel dietAssignment({int id = 1}) => DietAssignmentModel(
      id: id,
      customer: 2,
      dietPlan: 3,
      dietPlanName: 'High Protein Cut',
      customerName: 'Arjun Nair',
      startDate: DateTime(2026, 10, 2),
      createdAt: DateTime(2026, 10, 2),
      updatedAt: DateTime(2026, 10, 2),
    );

/// Recording fake for [PlanAssignmentRemoteDataSource].
class FakePlanAssignmentRemoteDataSource
    implements PlanAssignmentRemoteDataSource {
  List<WorkoutAssignmentModel> workoutResult = const [];
  List<DietAssignmentModel> dietResult = const [];
  Object? workoutError;
  Object? dietError;
  int workoutCalls = 0;
  int dietCalls = 0;

  @override
  Future<List<WorkoutAssignmentModel>> fetchActiveWorkoutAssignments() async {
    workoutCalls++;
    final error = workoutError;
    if (error != null) throw error;
    return workoutResult;
  }

  @override
  Future<List<DietAssignmentModel>> fetchActiveDietAssignments() async {
    dietCalls++;
    final error = dietError;
    if (error != null) throw error;
    return dietResult;
  }
}

/// Repository fake backed by [FakePlanAssignmentRemoteDataSource], mirroring
/// the real repository's Failure-to-record conversion.
class FakePlanAssignmentRepository implements PlanAssignmentRepository {
  FakePlanAssignmentRepository(this._remote);

  final FakePlanAssignmentRemoteDataSource _remote;

  @override
  Future<({List<WorkoutAssignmentModel>? assignments, Failure? error})>
      activeWorkoutAssignments() =>
          _map(_remote.fetchActiveWorkoutAssignments());

  @override
  Future<({List<DietAssignmentModel>? assignments, Failure? error})>
      activeDietAssignments() => _map(_remote.fetchActiveDietAssignments());

  Future<({List<T>? assignments, Failure? error})> _map<T>(
    Future<List<T>> future,
  ) async {
    try {
      return (assignments: await future, error: null);
    } on Failure catch (e) {
      return (assignments: null, error: e);
    }
  }
}
