import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/access/data/data_sources/tenant_lookup_remote_data_source.dart';

/// Builds a canned response for a request.
Future<Response<dynamic>> _response(
  RequestOptions options,
  int statusCode,
  Object? data,
) async {
  return Response<dynamic>(
    requestOptions: options,
    statusCode: statusCode,
    data: data,
  );
}

void main() {
  const gymUuid = '3f7c1a2b-4d5e-6f70-8192-a3b4c5d6e7f8';

  group('TenantLookupRemoteDataSource.lookupByCode', () {
    test('returns the gym for a known code', () async {
      final dio = Dio();
      dio.httpClientAdapter = _RecordingAdapter(
        (options) async => _response(
          options,
          200,
          {'uuid': gymUuid, 'name': 'Hash Fit'},
        ),
      );
      final source = TenantLookupRemoteDataSource(dio);

      final gym = await source.lookupByCode('HASHFIT');

      expect(gym.uuid, gymUuid);
      expect(gym.name, 'Hash Fit');
    });

    test('sends the code as a query parameter', () async {
      late Uri requestedUri;
      final dio = Dio();
      dio.httpClientAdapter = _RecordingAdapter(
        (options) async {
          requestedUri = options.uri;
          return _response(options, 200, {'uuid': gymUuid, 'name': 'Hash Fit'});
        },
      );
      final source = TenantLookupRemoteDataSource(dio);

      await source.lookupByCode('HASHFIT');

      expect(requestedUri.path, '/tenants/lookup/');
      expect(requestedUri.queryParameters['code'], 'HASHFIT');
    });

    test('a 404 becomes a ServerFailure (not a crash)', () async {
      final dio = Dio();
      dio.httpClientAdapter = _RecordingAdapter(
        (options) async => _response(options, 404, {'detail': 'Gym not found.'}),
      );
      final source = TenantLookupRemoteDataSource(dio);

      await expectLater(
        source.lookupByCode('NOPE'),
        throwsA(
          isA<ServerFailure>()
              .having((f) => f.statusCode, 'statusCode', 404)
              .having((f) => f.message, 'message', 'Gym not found.'),
        ),
      );
    });

    test('a 429 (throttled) becomes a ServerFailure', () async {
      final dio = Dio();
      dio.httpClientAdapter = _RecordingAdapter(
        (options) async => _response(options, 429, {'detail': 'Too many requests.'}),
      );
      final source = TenantLookupRemoteDataSource(dio);

      await expectLater(
        source.lookupByCode('HASHFIT'),
        throwsA(isA<ServerFailure>()),
      );
    });

    test('a response without a uuid is treated as not found', () async {
      final dio = Dio();
      dio.httpClientAdapter = _RecordingAdapter(
        (options) async => _response(options, 200, {'name': 'Hash Fit'}),
      );
      final source = TenantLookupRemoteDataSource(dio);

      await expectLater(
        source.lookupByCode('HASHFIT'),
        throwsA(isA<ServerFailure>()),
      );
    });

    test('a response with a null gym name falls back to a generic name', () async {
      final dio = Dio();
      dio.httpClientAdapter = _RecordingAdapter(
        (options) async => _response(options, 200, {'uuid': gymUuid, 'name': null}),
      );
      final source = TenantLookupRemoteDataSource(dio);

      final gym = await source.lookupByCode('HASHFIT');

      expect(gym.uuid, gymUuid);
      expect(gym.name, 'your gym');
    });
  });
}

/// A tiny [HttpClientAdapter] that answers with a canned JSON body and
/// status code — no real network, no mocking framework.
///
/// A non-2xx status is surfaced the way Dio does it: the response is
/// rejected with a [DioException] carrying the status code, so the data
/// source's error mapping is exercised for real.
class _RecordingAdapter implements HttpClientAdapter {
  _RecordingAdapter(this.handler);

  final Future<Response<dynamic>> Function(RequestOptions options) handler;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final response = await handler(options);
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
