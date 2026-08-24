import '../../../../core/errors/failures.dart';
import '../../data/data_sources/progress_remote_data_source.dart';
import '../../data/models/body_measurement.dart';

/// Repository for progress-related operations.
class ProgressRepository {
  final ProgressRemoteDataSource _remote;

  ProgressRepository(this._remote);

  /// Fetches the body measurements for a customer.
  Future<({List<BodyMeasurement> measurements, Failure? error})> getMeasurements(
    int customerId,
  ) async {
    try {
      final measurements = await _remote.getMeasurements(customerId);
      return (measurements: measurements, error: null);
    } on Failure catch (e) {
      return (measurements: const <BodyMeasurement>[], error: e);
    } catch (e) {
      return (measurements: const <BodyMeasurement>[], error: UnknownFailure(message: e.toString()));
    }
  }

  /// Fetches the fitness goals for a customer.
  Future<({List<FitnessGoal> goals, Failure? error})> getFitnessGoals(
    int customerId,
  ) async {
    try {
      final goals = await _remote.getFitnessGoals(customerId);
      return (goals: goals, error: null);
    } on Failure catch (e) {
      return (goals: const <FitnessGoal>[], error: e);
    } catch (e) {
      return (goals: const <FitnessGoal>[], error: UnknownFailure(message: e.toString()));
    }
  }
}
