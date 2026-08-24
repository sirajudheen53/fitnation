import '../../../../core/errors/failures.dart';
import '../../data/data_sources/ai_nutrition_remote_data_source.dart';
import '../../models/meal_plan.dart';
import '../../models/shopping_list_item.dart';

/// Repository for AI Nutrition operations.
class AiNutritionRepository {
  final AiNutritionRemoteDataSource _remote;

  AiNutritionRepository(this._remote);

  /// Fetches meal plans for the customer.
  Future<({List<MealPlan>? plans, Failure? error})> getMealPlans() async {
    try {
      final plans = await _remote.getMealPlans();
      return (plans: plans, error: null);
    } on Failure catch (e) {
      return (plans: null, error: e);
    } catch (e) {
      return (plans: null, error: UnknownFailure(message: e.toString()));
    }
  }

  /// Generates a new meal plan.
  Future<({MealPlan? plan, Failure? error})> generateMealPlan(
    Map<String, dynamic> preferences,
  ) async {
    try {
      final plan = await _remote.generateMealPlan(preferences);
      return (plan: plan, error: null);
    } on Failure catch (e) {
      return (plan: null, error: e);
    } catch (e) {
      return (plan: null, error: UnknownFailure(message: e.toString()));
    }
  }

  /// Fetches the shopping list for a meal plan.
  Future<({List<ShoppingListItem>? items, Failure? error})> getShoppingList({
    int? planId,
  }) async {
    try {
      final items = await _remote.getShoppingList(planId: planId);
      return (items: items, error: null);
    } on Failure catch (e) {
      return (items: null, error: e);
    } catch (e) {
      return (items: null, error: UnknownFailure(message: e.toString()));
    }
  }

  /// Tracks daily macro intake.
  Future<({bool success, Failure? error})> trackMacros(
    Map<String, dynamic> data,
  ) async {
    try {
      await _remote.trackMacros(data);
      return (success: true, error: null);
    } on Failure catch (e) {
      return (success: false, error: e);
    } catch (e) {
      return (success: false, error: UnknownFailure(message: e.toString()));
    }
  }
}
