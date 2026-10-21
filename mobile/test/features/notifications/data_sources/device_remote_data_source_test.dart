import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/notifications/data/data_sources/device_remote_data_source.dart';

void main() {
  const token = 'fcm-token-abc123';
  const endpoint = '/notifications/device-tokens/';

  group('DeviceRemoteDataSource.register', () {
    test('posts the FCM token to the device-tokens endpoint', () async {
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
      expect(call.recorded, hasLength(1));
      expect(call.recorded.single.method, 'POST');
      expect(call.recorded.single.uri.path, endpoint);
      final body = call.recorded.single.body as Map<String, dynamic>;
      expect(body['token'], token);
      expect(body['device_id'], 'device-1');
      expect(body['platform'], 'android');
    });

    test('a 200 re-registration is also accepted', () async {
      final dio = Dio();
      dio.httpClientAdapter = _CannedAdapter(
        calls: [() => _response(200, {'id': 7})],
      );
      final source = DeviceRemoteDataSource(dio);

      await source.register(
        token: token,
        deviceId: 'device-1',
        platform: 'android',
      );
    });

    test('a server error becomes a ServerFailure carrying the detail', () async {
      final dio = Dio();
      dio.httpClientAdapter = _CannedAdapter(
        calls: [() => _response(500, {'detail': 'Push backend down'})],
      );
      final source = DeviceRemoteDataSource(dio);

      await expectLater(
        source.register(
          token: token,
          deviceId: 'device-1',
          platform: 'android',
        ),
        throwsA(
          isA<ServerFailure>()
              .having((f) => f.statusCode, 'statusCode', 500)
              .having((f) => f.message, 'message', 'Push backend down'),
        ),
      );
    });

    test('a connection failure becomes a NetworkFailure', () async {
      final dio = Dio();
      dio.httpClientAdapter = _CannedAdapter(
        throws: () => DioException(
          requestOptions: RequestOptions(path: endpoint),
          type: DioExceptionType.connectionError,
        ),
      );
      final source = DeviceRemoteDataSource(dio);

      await expectLater(
        source.register(
          token: token,
          deviceId: 'device-1',
          platform: 'android',
        ),
        throwsA(isA<NetworkFailure>()),
      );
    });
  });

  group('DeviceRemoteDataSource.unregister', () {
    test('deletes the row whose token matches', () async {
      final dio = Dio();
      dio.httpClientAdapter = _CannedAdapter(
        calls: [
          () => _response(200, {
                'results': [
                  {'id': 3, 'token': 'other-device'},
                  {'id': 7, 'token': token},
                ],
              }),
          () => _response(204, null),
        ],
      );
      final source = DeviceRemoteDataSource(dio);

      await source.unregister(token);

      final adapter = dio.httpClientAdapter as _CannedAdapter;
      expect(adapter.recorded, hasLength(2));
      expect(adapter.recorded[0].method, 'GET');
      expect(adapter.recorded[1].method, 'DELETE');
      expect(adapter.recorded[1].uri.path, '${endpoint}7/');
    });

    test('understands a bare list body too', () async {
      final dio = Dio();
      dio.httpClientAdapter = _CannedAdapter(
        calls: [
          () => _response(200, [
                {'id': 12, 'token': token},
              ]),
          () => _response(204, null),
        ],
      );
      final source = DeviceRemoteDataSource(dio);

      await source.unregister(token);

      final adapter = dio.httpClientAdapter as _CannedAdapter;
      expect(adapter.recorded[1].uri.path, '${endpoint}12/');
    });

    test('an unlisted token deletes nothing', () async {
      final dio = Dio();
      dio.httpClientAdapter = _CannedAdapter(
        calls: [
          () => _response(200, {'results': []}),
        ],
      );
      final source = DeviceRemoteDataSource(dio);

      await source.unregister(token);

      final adapter = dio.httpClientAdapter as _CannedAdapter;
      expect(adapter.recorded, hasLength(1));
      expect(adapter.recorded.single.method, 'GET');
    });

    test('a 404 on the listing means it was already gone — success', () async {
      final dio = Dio();
      dio.httpClientAdapter = _CannedAdapter(
        calls: [() => _response(404, {'detail': 'Not found.'})],
      );
      final source = DeviceRemoteDataSource(dio);

      await source.unregister(token);

      final adapter = dio.httpClientAdapter as _CannedAdapter;
      expect(adapter.recorded, hasLength(1));
      expect(adapter.recorded.single.method, 'GET');
    });

    test('a listing failure other than 404 becomes a ServerFailure', () async {
      final dio = Dio();
      dio.httpClientAdapter = _CannedAdapter(
        calls: [() => _response(500, {'detail': 'DB error'})],
      );
      final source = DeviceRemoteDataSource(dio);

      await expectLater(
        source.unregister(token),
        throwsA(
          isA<ServerFailure>()
              .having((f) => f.statusCode, 'statusCode', 500)
              .having((f) => f.message, 'message', 'DB error'),
        ),
      );
    });
  });
}

/// Canned HTTP call record.
class _RecordedCall {
  final String method;
  final Uri uri;
  final Object? body;

  _RecordedCall(this.method, this.uri, this.body);
}

/// A tiny [HttpClientAdapter] that answers each request with a canned
/// response from a queue — no real network, no mocking framework.
///
/// A non-2xx status is surfaced the way Dio does it: the response is
/// rejected with a [DioException] carrying the status code, so the data
/// source's error mapping is exercised for real. Every request is recorded
/// into [recorded] so tests can assert on method, path, and payload.
class _CannedAdapter implements HttpClientAdapter {
  _CannedAdapter({
    List<Future<Response<dynamic>> Function()> calls = const [],
    this.throws,
  }) : _calls = List.of(calls);

  final List<Future<Response<dynamic>> Function()> _calls;
  final DioException Function()? throws;
  final List<_RecordedCall> recorded = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final callIndex = recorded.length;
    recorded.add(_RecordedCall(options.method, options.uri, options.data));
    final thrown = throws;
    if (thrown != null) throw thrown();
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

Future<Response<dynamic>> _response(int statusCode, Object? data) async {
  return Response<dynamic>(
    requestOptions: RequestOptions(path: '/'),
    statusCode: statusCode,
    data: data,
  );
}