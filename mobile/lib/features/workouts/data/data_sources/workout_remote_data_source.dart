import 'package:dio/dio.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/failures.dart';
import '../models/exercise.dart';
import '../models/workout_log.dart';
import '../models/workout_plan.dart';

/// Remote data source for workout-related endpoints.
class WorkoutRemoteDataSource {
  final Dio _dio;

  WorkoutRemoteDataSource(this._dio);

  /// Fetches the active workout assignment for a customer.
  ///
  /// GET /api/v1/workouts/workout-assignments/?customer={id}&is_active=true
  Future<WorkoutAssignment?> getActiveAssignment(int customerId) async {
    try {
      final response = await _dio.get(
        AppConstants.workoutAssignmentsEndpoint,
        queryParameters: {'customer': customerId, 'is_active': true},
      );
      final results = _extractResults(response.data);
      if (results.isEmpty) return null;
      return WorkoutAssignment.fromJson(results.first);
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Fetches a workout plan by id (with days and exercises).
  ///
  /// GET /api/v1/workouts/workout-plans/{id}/
  Future<WorkoutPlan> getWorkoutPlan(int planId) async {
    try {
      final response = await _dio.get(
        '${AppConstants.workoutPlansEndpoint}$planId/',
      );
      return WorkoutPlan.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Fetches the exercise library, optionally filtered.
  ///
  /// GET /api/v1/exercises/exercises/?category=&difficulty=&muscle_group=
  Future<List<Exercise>> getExercises({
    String? category,
    String? difficulty,
    String? muscleGroup,
  }) async {
    try {
      final response = await _dio.get(
        AppConstants.exercisesEndpoint,
        queryParameters: {
          'category': ?category,
          'difficulty': ?difficulty,
          'muscle_group': ?muscleGroup,
        },
      );
      final results = _extractResults(response.data);
      return results
          .map((e) => Exercise.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Fetches a single exercise by id.
  ///
  /// GET /api/v1/exercises/exercises/{id}/
  Future<Exercise> getExercise(int id) async {
    try {
      final response = await _dio.get('${AppConstants.exercisesEndpoint}$id/');
      return Exercise.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Logs a completed workout.
  ///
  /// POST /api/v1/workouts/workout-logs/
  Future<WorkoutLog> logWorkout(WorkoutLog log) async {
    try {
      final response = await _dio.post(
        AppConstants.workoutLogsEndpoint,
        data: log.toJson(),
      );
      return WorkoutLog.fromJson(response.data as Map<String, dynamic>);
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
          final message = (data is Map ? data['detail'] : null) ?? 'Authentication failed';
          return AuthFailure(message: message.toString(), statusCode: statusCode);
        }
        if (statusCode == 400 && data is Map<String, dynamic>) {
          return ValidationFailure(
            message: 'Validation error',
            errors: data,
            statusCode: statusCode,
          );
        }
        final message = (data is Map ? data['detail'] : null) ?? 'Server error';
        return ServerFailure(message: message.toString(), statusCode: statusCode);
      case DioExceptionType.cancel:
      case DioExceptionType.badCertificate:
      case DioExceptionType.transformTimeout:
      case DioExceptionType.unknown:
        return UnknownFailure(message: e.message ?? 'Unknown error');
    }
  }
}
