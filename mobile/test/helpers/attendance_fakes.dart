import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/attendance/data/data_sources/attendance_remote_data_source.dart';
import 'package:fitnation_app/features/attendance/data/models/attendance_record_model.dart';
import 'package:fitnation_app/features/attendance/domain/repositories/attendance_repository.dart';

/// Canned check-in row shared across attendance tests.
AttendanceRecordModel attendanceRecord({
  int id = 1,
  DateTime? checkOutTime,
  bool checkOutIsAuto = false,
}) =>
    AttendanceRecordModel(
      id: id,
      checkInTime: DateTime(2026, 10, 28, 18, 4),
      checkOutTime: checkOutTime,
      checkOutIsAuto: checkOutIsAuto,
      status: 'present',
      method: 'qr',
      branchName: 'Main',
    );

/// Recording fake for [AttendanceRemoteDataSource].
class FakeAttendanceRemoteDataSource implements AttendanceRemoteDataSource {
  List<AttendanceRecordModel> checkInResult = const [];
  Object? checkInError;
  int checkInCalls = 0;

  @override
  Future<List<AttendanceRecordModel>> fetchMyCheckIns() async {
    checkInCalls++;
    final error = checkInError;
    if (error != null) throw error;
    return checkInResult;
  }
}

/// Repository fake backed by [FakeAttendanceRemoteDataSource], mirroring
/// the real repository's Failure-to-record conversion.
class FakeAttendanceRepository implements AttendanceRepository {
  FakeAttendanceRepository(this._remote);

  final FakeAttendanceRemoteDataSource _remote;

  @override
  Future<({CheckInSummary? summary, Failure? error})> myCheckInSummary() async {
    try {
      final records = await _remote.fetchMyCheckIns();
      return (summary: CheckInSummary.fromRecords(records), error: null);
    } on Failure catch (e) {
      return (summary: null, error: e);
    }
  }
}
