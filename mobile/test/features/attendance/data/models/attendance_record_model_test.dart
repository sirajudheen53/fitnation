import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/attendance/data/models/attendance_record_model.dart';

void main() {
  Map<String, dynamic> row({
    int id = 1,
    String? checkOutTime,
    bool checkOutIsAuto = false,
    bool includeOptionals = true,
  }) =>
      {
        'id': id,
        'customer': 5,
        'person_id': 5,
        'person_name': 'Arjun Nair',
        'person_type': 'customer',
        'person_is_deleted': false,
        'branch': 1,
        'branch_id': 1,
        if (includeOptionals) 'branch_name': 'Main',
        'check_in_time': '2026-10-28T18:04:00Z',
        'check_out_time': checkOutTime,
        'check_out_is_auto': checkOutIsAuto,
        if (includeOptionals) 'status': 'present',
        if (includeOptionals) 'method': 'qr',
        'date': '2026-10-28',
        'created_at': '2026-10-28T18:04:05Z',
        'updated_at': '2026-10-28T19:30:00Z',
      };

  group('AttendanceRecordModel', () {
    test('parses an open visit (null check-out)', () {
      final record = AttendanceRecordModel.fromJson(row());

      expect(record.id, 1);
      expect(record.checkInTime, DateTime.utc(2026, 10, 28, 18, 4));
      expect(record.checkOutTime, isNull);
      expect(record.checkOutIsAuto, isFalse);
      expect(record.status, 'present');
      expect(record.method, 'qr');
      expect(record.branchName, 'Main');
    });

    test('parses a completed visit with an auto check-out flag', () {
      final record = AttendanceRecordModel.fromJson(
        row(
          checkOutTime: '2026-10-28T19:30:00Z',
          checkOutIsAuto: true,
        ),
      );

      expect(record.checkOutTime, DateTime.utc(2026, 10, 28, 19, 30));
      expect(record.checkOutIsAuto, isTrue);
    });

    test('tolerates missing optional fields', () {
      final record = AttendanceRecordModel.fromJson(row(includeOptionals: false));

      expect(record.status, isNull);
      expect(record.method, isNull);
      expect(record.branchName, isNull);
    });

    test('equality is by id', () {
      expect(AttendanceRecordModel.fromJson(row()), AttendanceRecordModel.fromJson(row()));
      expect(
        AttendanceRecordModel.fromJson(row()),
        isNot(AttendanceRecordModel.fromJson(row(id: 2))),
      );
    });
  });

  group('CheckInSummary.fromRecords', () {
    AttendanceRecordModel openVisit({int id = 1}) =>
        AttendanceRecordModel(id: id, checkInTime: DateTime(2026, 10, 28, 18, 4));
    AttendanceRecordModel doneVisit({int id = 9}) => AttendanceRecordModel(
          id: id,
          checkInTime: DateTime(2026, 10, 27, 7, 0),
          checkOutTime: DateTime(2026, 10, 27, 8, 15),
        );

    test('empty list means never checked in', () {
      final summary = CheckInSummary.fromRecords(const []);

      expect(summary.isCheckedIn, isFalse);
      expect(summary.active, isNull);
      expect(summary.lastCompleted, isNull);
      expect(summary.latest, isNull);
    });

    test('an open visit means currently checked in', () {
      final summary = CheckInSummary.fromRecords([openVisit()]);

      expect(summary.isCheckedIn, isTrue);
      expect(summary.active, openVisit());
      expect(summary.latest, openVisit());
    });

    test('completed visits land in lastCompleted', () {
      final summary = CheckInSummary.fromRecords([doneVisit()]);

      expect(summary.isCheckedIn, isFalse);
      expect(summary.lastCompleted, doneVisit());
      expect(summary.latest, doneVisit());
    });

    test('derivation is independent of list order', () {
      // API promises most-recent-first, but the scan must not rely on it.
      final summary = CheckInSummary.fromRecords([doneVisit(), openVisit()]);

      expect(summary.active, openVisit());
      expect(summary.lastCompleted, doneVisit());
      expect(summary.isCheckedIn, isTrue);
    });

    test('keeps the first open / first completed row it meets', () {
      final summary = CheckInSummary.fromRecords([
        doneVisit(id: 9),
        doneVisit(id: 8),
        openVisit(id: 2),
        openVisit(id: 1),
      ]);

      expect(summary.active?.id, 2);
      expect(summary.lastCompleted?.id, 9);
    });

    test('summaries with equal records compare equal', () {
      expect(
        CheckInSummary.fromRecords([openVisit()]),
        CheckInSummary.fromRecords([openVisit()]),
      );
    });
  });
}
