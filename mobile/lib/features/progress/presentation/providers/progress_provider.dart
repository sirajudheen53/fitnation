import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/data/data_sources/api_client.dart';
import '../../../auth/presentation/providers/auth_notifier.dart';
import '../../data/data_sources/progress_remote_data_source.dart';
import '../../data/models/body_measurement.dart';
import '../../domain/repositories/progress_repository.dart';

/// Provides the ProgressRemoteDataSource.
final progressRemoteDataSourceProvider = Provider<ProgressRemoteDataSource>((ref) {
  final dio = ApiClient.getInstance();
  return ProgressRemoteDataSource(dio);
});

/// Provides the ProgressRepository.
final progressRepositoryProvider = Provider<ProgressRepository>((ref) {
  final remote = ref.read(progressRemoteDataSourceProvider);
  return ProgressRepository(remote);
});

/// Gets the current customer id from the auth state.
int? _currentCustomerId(Ref ref) {
  return ref.read(authProvider).user?.id;
}

/// Fetches the body measurements for the current customer.
final bodyMeasurementsProvider =
    FutureProvider<List<BodyMeasurement>>((ref) async {
  final customerId = _currentCustomerId(ref);
  if (customerId == null) return const [];
  final repo = ref.read(progressRepositoryProvider);
  final result = await repo.getMeasurements(customerId);
  if (result.error != null) throw result.error!;
  return result.measurements;
});

/// Fetches the fitness goals for the current customer.
final fitnessGoalsProvider = FutureProvider<List<FitnessGoal>>((ref) async {
  final customerId = _currentCustomerId(ref);
  if (customerId == null) return const [];
  final repo = ref.read(progressRepositoryProvider);
  final result = await repo.getFitnessGoals(customerId);
  if (result.error != null) throw result.error!;
  return result.goals;
});
