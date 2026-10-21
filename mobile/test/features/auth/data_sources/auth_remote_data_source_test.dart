import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/entitlement.dart';

void main() {
  const gymUuid = '3f7c1a2b-4d5e-6f70-8192-a3b4c5d6e7f8';

  late List<_RecordedCall> calls;
  late Dio dio;

  /// Wires a Dio whose adapter replays [responses] in order.
  void stub(List<int> statuses, [List<Object?> bodies = const []]) {
    calls = [];
    dio = Dio();
    dio.httpClientAdapter = _CannedAdapter(
      statuses: statuses,
      bodies: bodies,
      recorded: calls,
    );
  }

  group('requestOtp', () {
    test('posts the phone number to the otp request endpoint', () async {
      stub([200], [{}]);
      final source = AuthRemoteDataSource(dio);

      await source.requestOtp('+919876543210');

      expect(calls, hasLength(1));
      expect(calls.single.method, 'POST');
      expect(calls.single.uri.path, '/users/auth/otp/request/');
      final body = calls.single.body as Map<String, dynamic>;
      expect(body['phone'], '+919876543210');
      // No anchor yet: the key must be absent, not null.
      expect(body.containsKey('gym'), isFalse);
    });

    test('sends the gym anchor when one is known', () async {
      stub([200], [{}]);
      final source = AuthRemoteDataSource(dio);

      await source.requestOtp('+919876543210', gymAnchor: gymUuid);

      final body = calls.single.body as Map<String, dynamic>;
      expect(body['gym'], gymUuid);
    });

    test('an empty anchor is not sent', () async {
      stub([200], [{}]);
      final source = AuthRemoteDataSource(dio);

      await source.requestOtp('+919876543210', gymAnchor: '');

      final body = calls.single.body as Map<String, dynamic>;
      expect(body.containsKey('gym'), isFalse);
    });

    test('a server failure becomes a ServerFailure', () async {
      stub([500], [{'detail': 'Boom'}]);
      final source = AuthRemoteDataSource(dio);

      await expectLater(
        source.requestOtp('+919876543210'),
        throwsA(isA<ServerFailure>()
            .having((f) => f.statusCode, 'statusCode', 500)),
      );
    });

    test('a 429 (rate limited) becomes a ServerFailure', () async {
      stub([429], [{'detail': 'Too many requests'}]);
      final source = AuthRemoteDataSource(dio);

      await expectLater(
        source.requestOtp('+919876543210'),
        throwsA(isA<ServerFailure>()
            .having((f) => f.statusCode, 'statusCode', 429)),
      );
    });

    test('a connection error becomes a NetworkFailure', () async {
      dio = Dio();
      dio.httpClientAdapter = _FailingAdapter();
      final source = AuthRemoteDataSource(dio);

      await expectLater(
        source.requestOtp('+919876543210'),
        throwsA(isA<NetworkFailure>()),
      );
    });
  });

  group('verifyOtp', () {
    test('posts the otp with the device info and parses the response',
        () async {
      stub([200], [
        {
          'token': 'tok-1',
          'user': {'id': 7, 'role': 'customer', 'first_name': 'Raman'},
          'permissions': ['app.access'],
          'entitlement': {
            'status': 'active',
            'read_only': false,
            'plan_name': 'Monthly Unlimited',
            'gym': {'uuid': gymUuid, 'name': 'Hash Fit'},
          },
        }
      ]);
      final source = AuthRemoteDataSource(dio);

      final response = await source.verifyOtp(
        phone: '+919876543210',
        otp: '123456',
        deviceType: 'android',
        deviceId: 'device-1',
        userAgent: 'FitNationApp/Android 14',
        gymAnchor: gymUuid,
      );

      expect(response.token, 'tok-1');
      expect(response.permissions, contains('app.access'));
      expect(response.entitlement?.status, AppEntitlementStatus.active);
      expect(response.entitlement?.gymName, 'Hash Fit');

      final body = calls.single.body as Map<String, dynamic>;
      expect(body['phone'], '+919876543210');
      expect(body['otp'], '123456');
      expect(body['device_type'], 'android');
      expect(body['device_id'], 'device-1');
      expect(body['user_agent'], 'FitNationApp/Android 14');
      // FBOS-011 correction #6: the anchor rides on verify too.
      expect(body['gym'], gymUuid);
    });

    test('omits the optional device fields when they are unknown', () async {
      stub([200], [
        {
          'token': 'tok-1',
          'user': {'id': 7, 'role': 'customer', 'first_name': 'Raman'},
        }
      ]);
      final source = AuthRemoteDataSource(dio);

      await source.verifyOtp(
        phone: '+919876543210',
        otp: '123456',
        deviceType: 'android',
      );

      final body = calls.single.body as Map<String, dynamic>;
      expect(body.containsKey('device_id'), isFalse);
      expect(body.containsKey('user_agent'), isFalse);
      expect(body.containsKey('gym'), isFalse);
    });

    test('a response without an entitlement is tolerated (legacy backend)',
        () async {
      stub([200], [
        {
          'token': 'tok-1',
          'user': {'id': 7, 'role': 'customer', 'first_name': 'Raman'},
        }
      ]);
      final source = AuthRemoteDataSource(dio);

      final response = await source.verifyOtp(
        phone: '+919876543210',
        otp: '123456',
        deviceType: 'android',
      );

      expect(response.entitlement, isNull);
    });

    test('a 400 validation error surfaces the backend detail', () async {
      stub([400], [
        {'gym': ['No gym matches this phone number.']}
      ]);
      final source = AuthRemoteDataSource(dio);

      await expectLater(
        source.verifyOtp(
          phone: '+919876543210',
          otp: '000000',
          deviceType: 'android',
        ),
        throwsA(isA<ValidationFailure>()),
      );
    });

    test('a 401 becomes an AuthFailure', () async {
      stub([401], [{'detail': 'Invalid OTP'}]);
      final source = AuthRemoteDataSource(dio);

      await expectLater(
        source.verifyOtp(
          phone: '+919876543210',
          otp: '000000',
          deviceType: 'android',
        ),
        throwsA(isA<AuthFailure>()
            .having((f) => f.statusCode, 'statusCode', 401)),
      );
    });
  });

  group('fetchEntitlement', () {
    test('gets the live entitlement from the entitlement endpoint', () async {
      stub([200], [
        {
          'status': 'grace',
          'read_only': true,
          'plan_name': 'Monthly Unlimited',
          'end_date': '2026-10-14',
          'grace_end_date': '2026-10-21',
          'gym': {'uuid': gymUuid, 'name': 'Hash Fit'},
        }
      ]);
      final source = AuthRemoteDataSource(dio);

      final entitlement = await source.fetchEntitlement();

      expect(calls.single.method, 'GET');
      expect(calls.single.uri.path, '/users/auth/entitlement/');
      expect(entitlement.status, AppEntitlementStatus.grace);
      expect(entitlement.readOnly, isTrue);
      expect(entitlement.planName, 'Monthly Unlimited');
      expect(entitlement.endDate, DateTime(2026, 10, 14));
      expect(entitlement.graceEndDate, DateTime(2026, 10, 21));
      expect(entitlement.gymUuid, gymUuid);
    });

    test('a 403 becomes an AuthFailure', () async {
      stub([403], [{'detail': 'Not a member'}]);
      final source = AuthRemoteDataSource(dio);

      await expectLater(
        source.fetchEntitlement(),
        throwsA(isA<AuthFailure>()),
      );
    });
  });

  group('getCurrentUser', () {
    test('gets the profile from the me endpoint', () async {
      stub([200], [
        {
          'token': 'tok-1',
          'user': {'id': 7, 'role': 'customer', 'first_name': 'Raman'},
          'permissions': ['app.access'],
          'entitlement': {'status': 'active'},
        }
      ]);
      final source = AuthRemoteDataSource(dio);

      final response = await source.getCurrentUser();

      expect(calls.single.method, 'GET');
      expect(calls.single.uri.path, '/users/auth/me/');
      expect(response.user.id, 7);
      expect(response.entitlement?.status, AppEntitlementStatus.active);
    });
  });

  group('logout', () {
    test('posts to the logout endpoint', () async {
      stub([200], [{}]);
      final source = AuthRemoteDataSource(dio);

      await source.logout();

      expect(calls.single.method, 'POST');
      expect(calls.single.uri.path, '/users/auth/logout/');
    });

    test('a 401 is swallowed — the session is gone either way', () async {
      stub([401], [{'detail': 'Invalid token'}]);
      final source = AuthRemoteDataSource(dio);

      // Must not throw: logging out with an already-invalid token is fine.
      await source.logout();
    });

    test('a 500 is surfaced', () async {
      stub([500], [{'detail': 'Boom'}]);
      final source = AuthRemoteDataSource(dio);

      await expectLater(source.logout(), throwsA(isA<ServerFailure>()));
    });
  });
}

/// A recorded request (method, target and body).
class _RecordedCall {
  _RecordedCall(this.method, this.uri, this.body);

  final String method;
  final Uri uri;
  final Object? body;
}

/// A Dio adapter that replays canned responses and records the requests.
class _CannedAdapter implements HttpClientAdapter {
  _CannedAdapter({
    required this.statuses,
    required this.bodies,
    required this.recorded,
  });

  final List<int> statuses;
  final List<Object?> bodies;
  final List<_RecordedCall> recorded;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final index = recorded.length;
    recorded.add(_RecordedCall(options.method, options.uri, options.data));
    final status = statuses[index];
    final body = jsonEncode(bodies[index]);

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
      response: Response<dynamic>(
        requestOptions: options,
        statusCode: status,
        data: bodies[index],
      ),
      type: DioExceptionType.badResponse,
    );
  }

  @override
  void close({bool force = false}) {}
}

/// A Dio adapter that always fails with a connection error.
class _FailingAdapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    throw DioException(
      requestOptions: options,
      type: DioExceptionType.connectionError,
      error: 'no network',
    );
  }

  @override
  void close({bool force = false}) {}
}
