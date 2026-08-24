import '../../../../core/errors/failures.dart';
import '../data/data_sources/workout_remote_data_source.dart';
import '../data/models/exercise.dart';
import '../data/models/workout_log.dart';
import '../data/models/workout_plan.dart';

/// Repository for workout-related operations.
class WorkoutRepository {
  final WorkoutRemoteDataSource _remote;

  WorkoutRepository(this._remote);

  /// Fetches the active workout assignment for a customer.
  Future<({WorkoutAssignment? assignment, Failure? error})> getActiveAssignment(
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

  /// Fetches a workout plan by id.
  Future<({WorkoutPlan? plan, Failure? error})> getWorkoutPlan(int planId) async {
    try {
      final plan = await _remote.getWorkoutPlan(planId);
      return (plan: plan, error: null);
    } on Failure catch (e) {
      return (plan: null, error: e);
    } catch (e) {
      return (plan: null, error: UnknownFailure(message: e.toString()));
    }
  }

  /// Fetches the exercise library.
  Future<({List<Exercise> exercises, Failure? error})> getExercises({
    String? category,
    String? difficulty,
    String? muscleGroup,
  }) async {
    try {
      final exercises = await _remote.getExercises(
        category: category,
        difficulty: difficulty,
        muscleGroup: muscleGroup,
      );
      return (exercises: exercises, error: null);
    } on Failure catch (e) {
      return (exercises: const [], error: e);
    } catch (e) {
      return (exercises: const [], error: UnknownFailure(message: e.toString()));
    }
  }

  /// Logs a completed workout.
  Future<({WorkoutLog? log, Failure? error})> logWorkout(WorkoutLog log) async {
    try {
      final created = await _remote.logWorkout(log);
      return (log: created, error: null);
    } on Failure catch (e) {
      return (log: null, error: e);
    } catch (e) {
      return (log: null, error: UnknownFailure(message: e.toString()));
    }
  }
}
