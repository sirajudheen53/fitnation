import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/data/data_sources/api_client.dart';
import '../../../auth/presentation/providers/auth_notifier.dart';
import '../../data/data_sources/diet_remote_data_source.dart';
import '../../data/models/diet_plan.dart';
import '../../data/models/meal.dart';
import '../../domain/repositories/diet_repository.dart';

/// Provides the DietRemoteDataSource.
final dietRemoteDataSourceProvider = Provider<DietRemoteDataSource>((ref) {
  final dio = ApiClient.getInstance();
  return DietRemoteDataSource(dio);
});

/// Provides the DietRepository.
final dietRepositoryProvider = Provider<DietRepository>((ref) {
  final remote = ref.read(dietRemoteDataSourceProvider);
  return DietRepository(remote);
});

/// Gets the current customer id from the auth state.
int? _currentCustomerId(Ref ref) {
  return ref.read(authProvider).user?.id;
}

/// Fetches the active diet assignment for the current customer.
final activeDietAssignmentProvider =
    FutureProvider<DietAssignment?>((ref) async {
  final customerId = _currentCustomerId(ref);
  if (customerId == null) return null;
  final repo = ref.read(dietRepositoryProvider);
  final result = await repo.getActiveAssignment(customerId);
  if (result.error != null) throw result.error!;
  return result.assignment;
});

/// Fetches a diet plan by id.
final dietPlanProvider =
    FutureProvider.family<DietPlan, int>((ref, planId) async {
  final repo = ref.read(dietRepositoryProvider);
  final result = await repo.getDietPlan(planId);
  if (result.error != null) throw result.error!;
  return result.plan!;
});

/// State for marking meals complete.
class MealLogState {
  final bool isLoading;
  final bool isSuccess;
  final String? errorMessage;

  const MealLogState({
    this.isLoading = false,
    this.isSuccess = false,
    this.errorMessage,
  });

  MealLogState copyWith({
    bool? isLoading,
    bool? isSuccess,
    String? errorMessage,
  }) {
    return MealLogState(
      isLoading: isLoading ?? this.isLoading,
      isSuccess: isSuccess ?? this.isSuccess,
      errorMessage: errorMessage,
    );
  }
}

/// Notifier for marking meals complete.
class MealLogNotifier extends StateNotifier<MealLogState> {
  MealLogNotifier() : super(const MealLogState());

  /// Simulates marking a meal complete.
  /// In a full implementation this would call the backend.
  Future<bool> markMealComplete(Meal meal) async {
    state = state.copyWith(isLoading: true, errorMessage: null, isSuccess: false);
    // TODO: Wire to backend endpoint when available.
    await Future.delayed(const Duration(milliseconds: 300));
    state = const MealLogState(isLoading: false, isSuccess: true);
    return true;
  }

  void reset() {
    state = const MealLogState();
  }
}

/// Provides the MealLogNotifier.
final mealLogProvider =
    StateNotifierProvider<MealLogNotifier, MealLogState>((ref) {
  return MealLogNotifier();
});
