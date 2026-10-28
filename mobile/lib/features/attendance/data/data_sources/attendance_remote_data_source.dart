import 'package:dio/dio.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/dio_failure_mapper.dart';
import '../../../../core/errors/failures.dart';
import '../models/attendance_record_model.dart';

/// Remote data source for the logged-in customer's check-ins (issue #95).
///
/// Follows the auth data source contract: failures are thrown as [Failure],
/// the repository converts them to result records.
class AttendanceRemoteDataSource {
  final Dio _dio;

  AttendanceRemoteDataSource(this._dio);

  /// Fetches the customer's own check-ins, most recent first.
  ///
  /// GET /api/v1/attendance/attendance/ — the backend force-filters the
  /// queryset to the caller's own records for customer-role tokens. The
  /// home card needs the latest state, not full history, so only the first
  /// (DRF-paginated) page is read.
  Future<List<AttendanceRecordModel>> fetchMyCheckIns() async {
    try {
      final response = await _dio.get(AppConstants.attendanceListEndpoint);
      final data = response.data as Map<String, dynamic>;
      final results = data['results'] as List<dynamic>;
      return results
          .map((e) =>
              AttendanceRecordModel.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw mapDioFailure(e);
    }
  }
}
