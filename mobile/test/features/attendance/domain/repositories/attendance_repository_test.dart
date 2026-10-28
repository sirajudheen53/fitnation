import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/attendance/domain/repositories/attendance_repository.dart';

import '../../../../helpers/attendance_fakes.dart';
import '../../../../helpers/fakes.dart';

void main() {
  late FakeAttendanceRemoteDataSource remote;
  late AttendanceRepository repository;

  setUp(() {
    remote = FakeAttendanceRemoteDataSource();
    repository = AttendanceRepository(remote);
  });

  test('returns the derived summary on success', () async {
    remote.checkInResult = [attendanceRecord()];

    final result = await repository.myCheckInSummary();

    expect(result.error, isNull);
    expect(result.summary, isNotNull);
    expect(result.summary!.isCheckedIn, isTrue);
  });

  test('empty history yields an empty summary, not an error', () async {
    final result = await repository.myCheckInSummary();

    expect(result.error, isNull);
    expect(result.summary!.isCheckedIn, isFalse);
    expect(result.summary!.latest, isNull);
  });

  test('a Failure from the data source becomes the error', () async {
    remote.checkInError = const AuthFailure(message: 'Not authorized');

    final result = await repository.myCheckInSummary();

    expectFailure(result.error, AuthFailure, messageContains: 'Not authorized');
    expect(result.summary, isNull);
  });

  test('an unexpected error becomes an UnknownFailure', () async {
    remote.checkInError = Exception('boom');

    final result = await repository.myCheckInSummary();

    expectFailure(result.error, UnknownFailure);
    expect(result.summary, isNull);
  });
}
