import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/data/data_sources/api_client.dart';
import '../../auth/presentation/providers/auth_notifier.dart';
import '../data/data_sources/workout_remote_data_source.dart';
import '../data/models/exercise.dart';
import '../data/models/workout_log.dart';
import '../data/models/workout_plan.dart';
import '../domain/repositories/workout_repository.dart';

/// Provides the WorkoutRemoteDataSource.
final workoutRemoteDataSourceProvider = Provider<WorkoutRemoteDataSource>((ref) {
  final dio = ApiClient.getInstance();
  return WorkoutRemoteDataSource(dio);
});

/// Provides the WorkoutRepository.
final workoutRepositoryProvider = Provider<WorkoutRepository>((ref) {
  final remote = ref.read(workoutRemoteDataSourceProvider);
  return WorkoutRepository(remote);
});

/// Gets the current customer id from the auth state.
int? _currentCustomerId(Ref ref) {
  return ref.read(authProvider).user?.id;
}

/// Fetches the active workout assignment for the current customer.
final activeWorkoutAssignmentProvider =
    FutureProvider<WorkoutAssignment?>((ref) async {
  final customerId = _currentCustomerId(ref);
  if (customerId == null) return null;
  final repo = ref.read(workoutRepositoryProvider);
  final result = await repo.getActiveAssignment(customerId);
  if (result.error != null) throw result.error!;
  return result.assignment;
});

/// Fetches a workout plan by id.
final workoutPlanProvider =
    FutureProvider.family<WorkoutPlan, int>((ref, planId) async {
  final repo = ref.read(workoutRepositoryProvider);
  final result = await repo.getWorkoutPlan(planId);
  if (result.error != null) throw result.error!;
  return result.plan!;
});

/// Fetches the exercise library.
final exerciseLibraryProvider = FutureProvider<List<Exercise>>((ref) async {
  final repo = ref.read(workoutRepositoryProvider);
  final result = await repo.getExercises();
  if (result.error != null) throw result.error!;
  return result.exercises;
});

/// State for logging a workout.
class WorkoutLogState {
  final bool isLoading;
  final bool isSuccess;
  final String? errorMessage;
  final WorkoutLog? log;

  const WorkoutLogState({
    this.isLoading = false,
    this.isSuccess = false,
    this.errorMessage,
    this.log,
  });

  WorkoutLogState copyWith({
    bool? isLoading,
    bool? isSuccess,
    String? errorMessage,
    WorkoutLog? log,
  }) {
    return WorkoutLogState(
      isLoading: isLoading ?? this.isLoading,
      isSuccess: isSuccess ?? this.isSuccess,
      errorMessage: errorMessage,
      log: log ?? this.log,
    );
  }
}

/// Notifier for logging a workout.
class WorkoutLogNotifier extends StateNotifier<WorkoutLogState> {
  final WorkoutRepository _repository;

  WorkoutLogNotifier(this._repository) : super(const WorkoutLogState());

  Future<bool> logWorkout(WorkoutLog log) async {
    state = state.copyWith(isLoading: true, errorMessage: null, isSuccess: false);
    final result = await _repository.logWorkout(log);
    if (result.error != null) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: result.error!.message,
      );
      return false;
    }
    state = WorkoutLogState(isLoading: false, isSuccess: true, log: result.log);
    return true;
  }

  void reset() {
    state = const WorkoutLogState();
  }
}

/// Provides the WorkoutLogNotifier.
final workoutLogProvider =
    StateNotifierProvider<WorkoutLogNotifier, WorkoutLogState>((ref) {
  return WorkoutLogNotifier(ref.read(workoutRepositoryProvider));
});
