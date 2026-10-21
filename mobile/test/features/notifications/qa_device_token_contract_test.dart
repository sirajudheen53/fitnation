/// QA regression test: the FCM device-token registration contract.
///
/// Pins the gap found during the FBOS-011 end-to-end verification
/// (docs/qa/app-access-e2e-verification.md): the backend's device-token
/// endpoint documents itself as an idempotent upsert ("201 on first
/// registration, 200 on re-registration"), but `DeviceToken.token` is
/// `unique=True`, so DRF's auto-generated `UniqueValidator` rejects the
/// second registration with **400** before the view's `update_or_create`
/// can run.
///
/// Impact on the app: after a re-install or an FCM token rotation the
/// registration is rejected, the member silently loses push, and
/// `_lastRegisteredToken` is never set — so the logout cleanup cannot
/// remove a row it never created.
///
/// This test is a regression guard, not a fix.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/notifications/data/data_sources/device_remote_data_source.dart';

void main() {
  const token = 'fcm-token-qa-1';
  const endpoint = '/notifications/device-tokens/';

  group('DeviceRemoteDataSource.register — the re-registration contract', () {
    test('a re-registration of the same token is accepted (201 or 200)', () async {
      // The backend contract: "201 on first registration, 200 on
      // re-registration". A duplicate token must NOT be an error.
      final dio = Dio();
      dio.httpClientAdapter = _CannedAdapter(
        calls: [
          () => _response(201, {'id': 7}),
          () => _response(200, {'id': 7}),
        ],
      );
      final source = DeviceRemoteDataSource(dio);

      await source.register(token: token, deviceId: 'device-1', platform: 'android');
      // The second registration of the SAME token must not throw.
      await source.register(token: token, deviceId: 'device-2', platform: 'android');

      final call = dio.httpClientAdapter as _CannedAdapter;
      expect(call.recorded, hasLength(2));
      // The rotation carried the new device id.
      final body = call.recorded.last.body as Map<String, dynamic>;
      expect(body['device_id'], 'device-2');
    });

    test('the registration payload matches the documented shape', () async {
      final dio = Dio();
      dio.httpClientAdapter = _CannedAdapter(
        calls: [() => _response(201, {'id': 7})],
      );
      final source = DeviceRemoteDataSource(dio);

      await source.register(
        token: token,
        deviceId: 'device-1',
        platform: 'android',
      );

      final call = dio.httpClientAdapter as _CannedAdapter;
      expect(call.recorded.single.method, 'POST');
      expect(call.recorded.single.uri.path, endpoint);
      final body = call.recorded.single.body as Map<String, dynamic>;
      expect(body['token'], token);
      expect(body['device_id'], 'device-1');
      expect(body['platform'], 'android');
      expect(body['device_type'], 'android');
    });

    test('a 400 duplicate-token response surfaces as a ServerFailure', () async {
      // This is the CURRENT backend behaviour (the defect): a duplicate
      // token is rejected with 400 by the UniqueValidator, so the app's
      // re-registration silently fails.
      //
      // Expected once QA-02 is fixed: 200 (upsert).
      // Actual on develop: 400 → the push registration is lost.
      final dio = Dio();
      dio.httpClientAdapter = _CannedAdapter(
        calls: [() => _response(400, {'token': ['device token with this token already exists.']})],
      );
      final source = DeviceRemoteDataSource(dio);

      await expectLater(
        source.register(token: token, deviceId: 'device-1', platform: 'android'),
        throwsA(
          isA<ServerFailure>()
              .having((f) => f.statusCode, 'statusCode', 400),
        ),
      );
    });
  });
}

/// A Dio adapter that replays canned responses and records the requests.
class _CannedAdapter implements HttpClientAdapter {
  _CannedAdapter({List<Future<Response<dynamic>> Function()> calls = const []})
      : _calls = List.of(calls);

  final List<Future<Response<dynamic>> Function()> _calls;
  final List<_RecordedCall> recorded = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final callIndex = recorded.length;
    recorded.add(_RecordedCall(options.method, options.uri, options.data));
    final response = await _calls[callIndex]();
    final status = response.statusCode ?? 200;
    final body = jsonEncode(response.data);

    if (status >= 200 && status < 300) {
      return ResponseBody.fromString(
        body,
        status,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );
    }

    throw DioException(
      requestOptions: options,
      response: response,
      type: DioExceptionType.badResponse,
    );
  }

  @override
  void close({bool force = false}) {}
}

/// A recorded request (method, target and body).
class _RecordedCall {
  _RecordedCall(this.method, this.uri, this.body);

  final String method;
  final Uri uri;
  final Object? body;
}

/// A minimal response carrying the given status and body.
Future<Response<dynamic>> _response(int statusCode, Object? data) async {
  return Response<dynamic>(
    requestOptions: RequestOptions(path: '/'),
    statusCode: statusCode,
    data: data,
  );
}
