import '../../../../core/errors/failures.dart';
import '../data/data_sources/attendance_remote_data_source.dart';
import '../data/models/attendance_record.dart';

/// Repository for attendance-related operations.
class AttendanceRepository {
  final AttendanceRemoteDataSource _remote;

  AttendanceRepository(this._remote);

  /// Fetches the attendance history for a customer.
  Future<({List<AttendanceRecord> records, Failure? error})> getHistory(
    int customerId,
  ) async {
    try {
      final records = await _remote.getAttendanceHistory(customerId);
      return (records: records, error: null);
    } on Failure catch (e) {
      return (records: const [], error: e);
    } catch (e) {
      return (records: const [], error: UnknownFailure(message: e.toString()));
    }
  }

  /// Performs a QR check-in.
  Future<({AttendanceRecord? record, Failure? error})> checkIn({
    required String qrCode,
    int? customerId,
  }) async {
    try {
      final record = await _remote.checkIn(qrCode: qrCode, customerId: customerId);
      return (record: record, error: null);
    } on Failure catch (e) {
      return (record: null, error: e);
    } catch (e) {
      return (record: null, error: UnknownFailure(message: e.toString()));
    }
  }
}
