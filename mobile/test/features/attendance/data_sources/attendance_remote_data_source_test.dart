import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/attendance/data/data_sources/attendance_remote_data_source.dart';
import '../../../helpers/canned_adapter.dart';

void main() {
  group('AttendanceRemoteDataSource.getAttendanceHistory', () {
    test('GETs the attendance records filtered by customer', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'results': [
                  {
                    'id': 1,
                    'customer': 10,
                    'check_in_time': '2026-06-01T08:00:00Z',
                    'check_out_time': '2026-06-01T09:30:00Z',
                    'status': 'present',
                    'method': 'qr',
                    'branch_name': 'Adyar',
                  },
                ],
              }),
        ],
      );
      final source = AttendanceRemoteDataSource(dio);

      final records = await source.getAttendanceHistory(10);

      expect(records, hasLength(1));
      expect(records.single.customerId, 10);
      expect(records.single.checkInTime, DateTime.parse('2026-06-01T08:00:00Z'));
      expect(records.single.status, 'present');
      expect(records.single.method, 'qr');
      expect(records.single.branchName, 'Adyar');

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.uri.path, '/attendance/attendance/');
      expect(call.recorded.single.uri.queryParameters['customer'], '10');
    });

    test('accepts a bare list body', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, [
                {'id': 2, 'status': 'late'},
              ]),
        ],
      );
      final source = AttendanceRemoteDataSource(dio);

      expect((await source.getAttendanceHistory(1)).single.status, 'late');
    });
  });

  group('AttendanceRemoteDataSource.checkIn', () {
    test('POSTs the QR code and optional customer', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(201, {
                'id': 3,
                'customer': 10,
                'status': 'present',
                'method': 'qr',
              }),
        ],
      );
      final source = AttendanceRemoteDataSource(dio);

      final record = await source.checkIn(qrCode: 'ATT-123', customerId: 10);

      expect(record.id, 3);
      expect(record.method, 'qr');

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.method, 'POST');
      expect(call.recorded.single.uri.path, '/attendance/check-in/');
      expect(call.recorded.single.bodyMap, {'qr_code': 'ATT-123', 'customer': 10});
    });

    test('omits the customer key when no id is given', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(201, {'id': 4})],
      );
      final source = AttendanceRemoteDataSource(dio);

      await source.checkIn(qrCode: 'ATT-9');

      final body = (dio.httpClientAdapter as CannedAdapter)
          .recorded.single.bodyMap as Map<String, dynamic>;
      expect(body, {'qr_code': 'ATT-9'});
    });

    test('a rejected QR maps to the failure ladder', () async {
      final invalid = Dio()..httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(400, {'qr_code': ['Expired QR']})],
      );
      await expectLater(
        AttendanceRemoteDataSource(invalid).checkIn(qrCode: 'OLD'),
        throwsA(
          isA<ValidationFailure>()
              .having((f) => f.statusCode, 'statusCode', 400)
              .having((f) => f.errors, 'errors', {'qr_code': ['Expired QR']}),
        ),
      );

      final down = Dio()..httpClientAdapter = CannedAdapter(
        throws: () => DioException(
          requestOptions: RequestOptions(path: '/x'),
          type: DioExceptionType.connectionError,
        ),
      );
      await expectLater(
        AttendanceRemoteDataSource(down).checkIn(qrCode: 'OK'),
        throwsA(isA<NetworkFailure>()),
      );
    });
  });
}