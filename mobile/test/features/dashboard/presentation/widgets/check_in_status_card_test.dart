import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/attendance/data/models/attendance_record_model.dart';
import 'package:fitnation_app/features/attendance/presentation/providers/check_in_providers.dart';
import 'package:fitnation_app/features/dashboard/presentation/widgets/check_in_status_card.dart';

import '../../../../helpers/attendance_fakes.dart';

void main() {
  AttendanceRecordModel openVisit() => attendanceRecord();
  AttendanceRecordModel doneVisit({bool auto = false}) => attendanceRecord(
        id: 9,
        checkOutTime: DateTime(2026, 10, 28, 19, 15),
        checkOutIsAuto: auto,
      );

  Future<void> pumpCard(
    WidgetTester tester,
    CheckInState state, {
    required void Function() onRetry,
  }) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: CheckInStatusCard(state: state, onRetry: () async => onRetry()),
        ),
      ),
    );
  }

  testWidgets('checked-in state shows the open visit', (tester) async {
    await pumpCard(
      tester,
      CheckInState(
        status: CheckInStatus.loaded,
        summary: CheckInSummary.fromRecords([openVisit()]),
      ),
      onRetry: () {},
    );

    expect(find.text('You\'re checked in'), findsOneWidget);
    expect(find.text('Since 6:04 PM at Main'), findsOneWidget);
    expect(find.text('Last visit 28 Oct 2026'), findsNothing);
  });

  testWidgets('last completed visit shows the check-out time', (tester) async {
    await pumpCard(
      tester,
      CheckInState(
        status: CheckInStatus.loaded,
        summary: CheckInSummary.fromRecords([doneVisit()]),
      ),
      onRetry: () {},
    );

    expect(find.text('Last visit 28 Oct 2026'), findsOneWidget);
    expect(find.text('Checked out at 7:15 PM'), findsOneWidget);
  });

  testWidgets('auto check-outs are called out', (tester) async {
    await pumpCard(
      tester,
      CheckInState(
        status: CheckInStatus.loaded,
        summary: CheckInSummary.fromRecords([doneVisit(auto: true)]),
      ),
      onRetry: () {},
    );

    expect(find.text('Checked out automatically at 7:15 PM'), findsOneWidget);
  });

  testWidgets('no history shows the empty state', (tester) async {
    await pumpCard(
      tester,
      const CheckInState(status: CheckInStatus.loaded),
      onRetry: () {},
    );

    expect(find.text('No visits yet'), findsOneWidget);
    expect(find.text('Your check-ins will show up here.'), findsOneWidget);
  });

  testWidgets('first load shows a compact loading row', (tester) async {
    await pumpCard(
      tester,
      const CheckInState(status: CheckInStatus.loading),
      onRetry: () {},
    );

    expect(find.text('Checking your visit status…'), findsOneWidget);
  });

  testWidgets('error shows the message and retry re-triggers the load', (
    tester,
  ) async {
    var retries = 0;
    await pumpCard(
      tester,
      const CheckInState(
        status: CheckInStatus.error,
        errorMessage: 'Your membership has expired.',
      ),
      onRetry: () => retries++,
    );

    expect(find.text('Your membership has expired.'), findsOneWidget);

    await tester.tap(find.text('Retry'));
    expect(retries, 1);
  });
}
