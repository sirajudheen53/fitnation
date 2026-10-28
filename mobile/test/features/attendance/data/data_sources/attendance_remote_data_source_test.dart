import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/auth/data/data_sources/api_client.dart';
import 'package:fitnation_app/features/attendance/data/data_sources/attendance_remote_data_source.dart';

import '../../../../helpers/fakes.dart';

void main() {
  Map<String, dynamic> attendanceRow({int id = 1, String? checkOutTime}) => {
        'id': id,
        'customer': 5,
        'person_id': 5,
        'person_name': 'Arjun Nair',
        'person_type': 'customer',
        'person_is_deleted': false,
        'branch': 1,
        'branch_id': 1,
        'branch_name': 'Main',
        'check_in_time': '2026-10-28T18:04:00Z',
        'check_out_time': checkOutTime,
        'check_out_is_auto': false,
        'status': 'present',
        'method': 'qr',
        'date': '2026-10-28',
        'created_at': '2026-10-28T18:04:05Z',
        'updated_at': '2026-10-28T19:30:00Z',
      };

  Map<String, dynamic> envelope(List<dynamic> results) =>
      {'count': results.length, 'next': null, 'previous': null, 'results': results};

  test('fetchMyCheckIns GETs the attendance list and parses the page', () async {
    final requests = <RequestOptions>[];
    final adapter = FakeDioAdapter((options) {
      requests.add(options);
      return FakeDioAdapter.json(envelope([
        attendanceRow(),
        attendanceRow(id: 2, checkOutTime: '2026-10-28T19:30:00Z'),
      ]));
    });
    final source = AttendanceRemoteDataSource(FakeDioAdapter.client(adapter));

    final records = await source.fetchMyCheckIns();

    expect(records, hasLength(2));
    expect(records.first.id, 1);
    expect(records.first.checkOutTime, isNull);
    expect(records.last.checkOutTime, isNotNull);
    expect(requests.single.method, 'GET');
    expect(requests.single.path, '/attendance/attendance/');
    // The backend self-scopes; the app must not send a customer filter.
    expect(requests.single.queryParameters, isEmpty);
  });

  test('a 403 surfaces as an AuthFailure with the backend detail', () async {
    final adapter = FakeDioAdapter((options) =>
        FakeDioAdapter.json({'detail': 'Membership required'}, 403));
    final source = AttendanceRemoteDataSource(FakeDioAdapter.client(adapter));

    await expectLater(
      source.fetchMyCheckIns(),
      throwsA(isA<AuthFailure>()),
    );
  });

  test('a 500 surfaces as a ServerFailure', () async {
    final adapter = FakeDioAdapter(
        (options) => FakeDioAdapter.json({'detail': 'Boom'}, 500));
    final source = AttendanceRemoteDataSource(FakeDioAdapter.client(adapter));

    await expectLater(
      source.fetchMyCheckIns(),
      throwsA(isA<ServerFailure>()),
    );
  });
}
