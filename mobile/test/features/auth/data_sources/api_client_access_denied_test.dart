import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/auth/data/data_sources/api_client.dart';

void main() {
  tearDown(() {
    ApiClient.onAccessDenied = null;
    ApiClient.reset();
  });

  /// The app's real Dio (which carries the access-denied interceptor),
  /// wired to answer every request with [status] and [body].
  Dio dioAnswering(int status, Map<String, dynamic> body) {
    final dio = ApiClient.getInstance();
    dio.httpClientAdapter = _StubAdapter(status, body);
    return dio;
  }

  group('403 app_access interception', () {
    test('app_access_required is surfaced to the app', () async {
      final codes = <String>[];
      ApiClient.onAccessDenied = codes.add;

      final dio = dioAnswering(403, {
        'detail': 'An active membership is required to use the app.',
        'code': 'app_access_required',
      });

      await expectLater(
        dio.get('/workouts/'),
        throwsA(isA<DioException>()),
      );

      expect(codes, ['app_access_required']);
    });

    test('app_access_read_only is surfaced to the app', () async {
      final codes = <String>[];
      ApiClient.onAccessDenied = codes.add;

      final dio = dioAnswering(403, {
        'detail': 'Your membership has expired — access is read-only.',
        'code': 'app_access_read_only',
      });

      await expectLater(
        dio.get('/workouts/'),
        throwsA(isA<DioException>()),
      );

      expect(codes, ['app_access_read_only']);
    });

    test('an unrelated 403 is not surfaced', () async {
      final codes = <String>[];
      ApiClient.onAccessDenied = codes.add;

      final dio = dioAnswering(403, {
        'detail': 'You do not have permission to perform this action.',
        'code': 'some_other_code',
      });

      await expectLater(
        dio.get('/workouts/'),
        throwsA(isA<DioException>()),
      );

      expect(codes, isEmpty);
    });

    test('a 403 without a code is not surfaced', () async {
      final codes = <String>[];
      ApiClient.onAccessDenied = codes.add;

      final dio = dioAnswering(403, {'detail': 'Forbidden'});

      await expectLater(
        dio.get('/workouts/'),
        throwsA(isA<DioException>()),
      );

      expect(codes, isEmpty);
    });

    test('a 200 response is not surfaced', () async {
      final codes = <String>[];
      ApiClient.onAccessDenied = codes.add;

      final dio = dioAnswering(200, {
        'detail': 'ok',
        'code': 'app_access_required',
      });

      await dio.get('/workouts/');

      expect(codes, isEmpty);
    });

    test('a 401 is not surfaced (that is an auth problem, not a gate)', () async {
      final codes = <String>[];
      ApiClient.onAccessDenied = codes.add;

      final dio = dioAnswering(401, {
        'detail': 'Authentication credentials were not provided.',
        'code': 'app_access_required',
      });

      await expectLater(
        dio.get('/workouts/'),
        throwsA(isA<DioException>()),
      );

      expect(codes, isEmpty);
    });

    test('no handler installed means no crash', () async {
      ApiClient.onAccessDenied = null;

      final dio = dioAnswering(403, {'code': 'app_access_required'});

      await expectLater(
        dio.get('/workouts/'),
        throwsA(isA<DioException>()),
      );
    });
  });
}

/// Answers every request with a fixed status and body.
class _StubAdapter implements HttpClientAdapter {
  _StubAdapter(this.status, this.body);

  final int status;
  final Map<String, dynamic> body;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    if (status >= 200 && status < 300) {
      return ResponseBody.fromString(
        jsonEncode(body),
        status,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );
    }
    throw DioException(
      requestOptions: options,
      response: Response<dynamic>(
        requestOptions: options,
        statusCode: status,
        data: body,
      ),
      type: DioExceptionType.badResponse,
    );
  }

  @override
  void close({bool force = false}) {}
}
