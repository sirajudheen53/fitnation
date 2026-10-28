import 'package:dio/dio.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/dio_failure_mapper.dart';
import '../../../../core/errors/failures.dart';
import '../models/diet_assignment_model.dart';
import '../models/workout_assignment_model.dart';

/// Remote data source for the customer's plan assignments (issues #90/#94).
///
/// Follows the auth data source contract: failures are thrown as [Failure],
/// the repository converts them to result records.
class PlanAssignmentRemoteDataSource {
  final Dio _dio;

  PlanAssignmentRemoteDataSource(this._dio);

  /// Fetches the logged-in customer's active workout assignments.
  ///
  /// GET /api/v1/workouts/workout-assignments/active/
  Future<List<WorkoutAssignmentModel>> fetchActiveWorkoutAssignments() async {
    try {
      final response =
          await _dio.get(AppConstants.workoutAssignmentsActiveEndpoint);
      final data = response.data as List<dynamic>;
      return data
          .map((e) =>
              WorkoutAssignmentModel.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw mapDioFailure(e);
    }
  }

  /// Fetches the logged-in customer's active diet (meal plan) assignments.
  ///
  /// GET /api/v1/diet-assignments/active/
  Future<List<DietAssignmentModel>> fetchActiveDietAssignments() async {
    try {
      final response = await _dio.get(AppConstants.dietAssignmentsActiveEndpoint);
      final data = response.data as List<dynamic>;
      return data
          .map((e) => DietAssignmentModel.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw mapDioFailure(e);
    }
  }
}
