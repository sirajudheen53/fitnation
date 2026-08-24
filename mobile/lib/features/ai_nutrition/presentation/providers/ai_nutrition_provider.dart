import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/data/data_sources/api_client.dart';
import '../../data/data_sources/ai_nutrition_remote_data_source.dart';
import '../../domain/repositories/ai_nutrition_repository.dart';
import '../../models/meal_plan.dart';
import '../../models/shopping_list_item.dart';

/// Provides the AiNutritionRemoteDataSource.
final aiNutritionRemoteDataSourceProvider =
    Provider<AiNutritionRemoteDataSource>((ref) {
  final dio = ApiClient.getInstance();
  return AiNutritionRemoteDataSource(dio);
});

/// Provides the AiNutritionRepository.
final aiNutritionRepositoryProvider = Provider<AiNutritionRepository>((ref) {
  final remote = ref.read(aiNutritionRemoteDataSourceProvider);
  return AiNutritionRepository(remote);
});

/// Fetches the customer's meal plans.
final mealPlansProvider = FutureProvider<List<MealPlan>>((ref) async {
  final repo = ref.read(aiNutritionRepositoryProvider);
  final result = await repo.getMealPlans();
  if (result.error != null) throw result.error!;
  return result.plans ?? const [];
});

/// Fetches the active meal plan (first plan, or a selected one).
final activeMealPlanProvider = Provider<MealPlan?>((ref) => null);

/// Fetches the shopping list for a given plan.
final shoppingListProvider =
    FutureProvider.family<List<ShoppingListItem>, int?>((ref, planId) async {
  final repo = ref.read(aiNutritionRepositoryProvider);
  final result = await repo.getShoppingList(planId: planId);
  if (result.error != null) throw result.error!;
  return result.items ?? const [];
});

/// State for generating a meal plan.
class GenerateState {
  final bool isLoading;
  final MealPlan? generatedPlan;
  final String? errorMessage;

  const GenerateState({
    this.isLoading = false,
    this.generatedPlan,
    this.errorMessage,
  });

  GenerateState copyWith({
    bool? isLoading,
    MealPlan? generatedPlan,
    String? errorMessage,
  }) {
    return GenerateState(
      isLoading: isLoading ?? this.isLoading,
      generatedPlan: generatedPlan ?? this.generatedPlan,
      errorMessage: errorMessage,
    );
  }
}

/// Notifier handling meal plan generation.
class GenerateNotifier extends StateNotifier<GenerateState> {
  final AiNutritionRepository _repository;

  GenerateNotifier(this._repository) : super(const GenerateState());

  /// Generates a meal plan from preferences.
  Future<MealPlan?> generate(Map<String, dynamic> preferences) async {
    state = state.copyWith(
      isLoading: true,
      errorMessage: null,
      generatedPlan: null,
    );
    final result = await _repository.generateMealPlan(preferences);
    if (result.error != null) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: result.error!.message,
      );
      return null;
    }
    state = GenerateState(isLoading: false, generatedPlan: result.plan);
    return result.plan;
  }

  void reset() {
    state = const GenerateState();
  }
}

/// Provides the GenerateNotifier.
final generatePlanProvider =
    StateNotifierProvider<GenerateNotifier, GenerateState>((ref) {
  return GenerateNotifier(ref.read(aiNutritionRepositoryProvider));
});
