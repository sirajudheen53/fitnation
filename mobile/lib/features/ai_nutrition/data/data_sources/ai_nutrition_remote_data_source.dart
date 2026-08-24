import 'package:dio/dio.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/failures.dart';
import '../../models/meal_plan.dart';
import '../../models/shopping_list_item.dart';

/// Remote data source for AI Nutrition.
class AiNutritionRemoteDataSource {
  final Dio _dio;

  AiNutritionRemoteDataSource(this._dio);

  /// Fetches meal plans for the customer.
  ///
  /// GET /api/v1/ai/nutrition/meal-plans/
  Future<List<MealPlan>> getMealPlans() async {
    try {
      final response = await _dio.get(AppConstants.nutritionMealPlansEndpoint);
      final results = _extractResults(response.data);
      return results
          .map((e) => MealPlan.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Generates a new meal plan from preferences.
  ///
  /// POST /api/v1/ai/nutrition/generate/
  Future<MealPlan> generateMealPlan(Map<String, dynamic> preferences) async {
    try {
      final response = await _dio.post(
        AppConstants.nutritionGenerateEndpoint,
        data: preferences,
      );
      return MealPlan.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Fetches the shopping list for a meal plan.
  ///
  /// GET /api/v1/ai/nutrition/shopping-list/?plan={id}
  Future<List<ShoppingListItem>> getShoppingList({int? planId}) async {
    try {
      final response = await _dio.get(
        AppConstants.nutritionShoppingListEndpoint,
        queryParameters: {if (planId != null) 'plan': planId},
      );
      final results = _extractResults(response.data);
      return results
          .map((e) => ShoppingListItem.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Tracks daily macro intake.
  ///
  /// POST /api/v1/ai/nutrition/macros/
  Future<void> trackMacros(Map<String, dynamic> data) async {
    try {
      await _dio.post(AppConstants.nutritionMacrosEndpoint, data: data);
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Extracts a list of results from a paginated or plain list response.
  List<dynamic> _extractResults(dynamic data) {
    if (data is List) return data;
    if (data is Map && data['results'] is List) {
      return data['results'] as List;
    }
    return const [];
  }

  /// Maps a DioException to a Failure.
  Failure _mapDioError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.connectionError:
        return const NetworkFailure();
      case DioExceptionType.badResponse:
        final statusCode = e.response?.statusCode;
        final data = e.response?.data;
        if (statusCode == 401 || statusCode == 403) {
          final message =
              (data is Map ? data['detail'] : null) ?? 'Authentication failed';
          return AuthFailure(message: message.toString(), statusCode: statusCode);
        }
        if (statusCode == 400 && data is Map<String, dynamic>) {
          return ValidationFailure(
            message: 'Validation error',
            errors: data,
            statusCode: statusCode,
          );
        }
        final message =
            (data is Map ? data['detail'] : null) ?? 'Server error';
        return ServerFailure(message: message.toString(), statusCode: statusCode);
      case DioExceptionType.cancel:
      case DioExceptionType.badCertificate:
      case DioExceptionType.transformTimeout:
      case DioExceptionType.unknown:
        return UnknownFailure(message: e.message ?? 'Unknown error');
    }
  }
}
