import '../../../../core/errors/failures.dart';
import '../../data/data_sources/attendance_remote_data_source.dart';
import '../../data/models/attendance_record_model.dart';

/// Repository for the logged-in customer's check-in state (issue #95).
class AttendanceRepository {
  final AttendanceRemoteDataSource _remote;

  AttendanceRepository(this._remote);

  /// Derived check-in summary (open visit + last completed visit) for the
  /// home card.
  Future<({CheckInSummary? summary, Failure? error})> myCheckInSummary() async {
    try {
      final records = await _remote.fetchMyCheckIns();
      return (summary: CheckInSummary.fromRecords(records), error: null);
    } on Failure catch (e) {
      return (summary: null, error: e);
    } catch (e) {
      return (summary: null, error: UnknownFailure(message: e.toString()));
    }
  }
}
