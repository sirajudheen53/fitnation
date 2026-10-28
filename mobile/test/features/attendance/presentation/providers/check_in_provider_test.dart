import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/attendance/presentation/providers/check_in_providers.dart';

import '../../../../helpers/attendance_fakes.dart';

void main() {
  late FakeAttendanceRemoteDataSource remote;
  late ProviderContainer container;

  setUp(() {
    remote = FakeAttendanceRemoteDataSource();
    container = ProviderContainer(
      overrides: [
        attendanceRepositoryProvider
            .overrideWithValue(FakeAttendanceRepository(remote)),
      ],
    );
  });

  tearDown(() => container.dispose());

  CheckInState state() => container.read(checkInProvider);

  test('starts idle before any load', () {
    expect(state().status, CheckInStatus.idle);
    expect(state().summary, isNull);
  });

  test('load transitions idle → loaded with the summary', () async {
    remote.checkInResult = [attendanceRecord()];

    await container.read(checkInProvider.notifier).load();

    expect(state().status, CheckInStatus.loaded);
    expect(state().summary!.isCheckedIn, isTrue);
    expect(state().errorMessage, isNull);
  });

  test('load surfaces the failure message on error', () async {
    remote.checkInError = const AuthFailure(message: 'Not authorized');

    await container.read(checkInProvider.notifier).load();

    expect(state().status, CheckInStatus.error);
    expect(state().errorMessage, 'Not authorized');
    expect(state().summary, isNull);
  });

  test('a refresh error keeps the previously loaded summary', () async {
    remote.checkInResult = [attendanceRecord()];
    await container.read(checkInProvider.notifier).load();

    remote.checkInError = const ServerFailure(message: 'Boom');
    await container.read(checkInProvider.notifier).load();

    expect(state().status, CheckInStatus.error);
    expect(state().summary, isNotNull);
  });

  test('a successful refresh replaces the summary', () async {
    remote.checkInResult = [attendanceRecord()];
    await container.read(checkInProvider.notifier).load();

    remote.checkInResult = [
      attendanceRecord(checkOutTime: DateTime(2026, 10, 28, 19, 30)),
    ];
    await container.read(checkInProvider.notifier).load();

    expect(state().status, CheckInStatus.loaded);
    expect(state().summary!.isCheckedIn, isFalse);
  });
}
