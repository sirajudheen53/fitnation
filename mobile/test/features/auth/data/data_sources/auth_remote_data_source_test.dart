import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';

import '../../../../helpers/fakes.dart';

void main() {
  late FakeDioAdapter adapter;
  late AuthRemoteDataSource dataSource;

  setUp(() {
    adapter = FakeDioAdapter(
      (options) => FakeDioAdapter.json(authResponseJson(), 200),
    );
    dataSource = AuthRemoteDataSource(FakeDioAdapter.client(adapter));
  });

  group('firebaseLogin', () {
    test('POSTs to /auth/firebase/ with id_token and device_type', () async {
      await dataSource.firebaseLogin(idToken: 'tok-1', deviceType: 'android');

      final request = adapter.requests.single;
      expect(request.uri.path, '/api/v1/auth/firebase/');
      expect(request.method, 'POST');
      expect(request.data['id_token'], 'tok-1');
      expect(request.data['device_type'], 'android');
      expect(request.data.containsKey('gym'), isFalse);
    });

    test('includes gym when provided', () async {
      await dataSource.firebaseLogin(
        idToken: 'tok-1',
        deviceType: 'android',
        gym: '7',
      );

      expect(adapter.requests.single.data['gym'], '7');
    });

    test('parses the AuthResponse (same shape as otp verify)', () async {
      final response = await dataSource.firebaseLogin(
        idToken: 'tok-1',
        deviceType: 'web',
      );

      expect(response.token, 'session-token-1');
      expect(response.user.id, 1);
      expect(response.permissions, ['workouts.view_workout']);
    });

    test('401 → AuthFailure (invalid/expired token)', () async {
      final ds = AuthRemoteDataSource(
        FakeDioAdapter.client(
          FakeDioAdapter(
            (_) => FakeDioAdapter.json({'detail': 'Invalid token'}, 401),
          ),
        ),
      );

      await expectLater(
        ds.firebaseLogin(idToken: 'tok', deviceType: 'web'),
        throwsA(isA<AuthFailure>()),
      );
    });

    test('429 → rate limit AuthFailure', () async {
      final ds = AuthRemoteDataSource(
        FakeDioAdapter.client(
          FakeDioAdapter(
            (_) => FakeDioAdapter.json({'detail': 'Throttled'}, 429),
          ),
        ),
      );

      Failure? caught;
      try {
        await ds.firebaseLogin(idToken: 't', deviceType: 'web');
      } on Failure catch (f) {
        caught = f;
      }
      expect(caught, isA<AuthFailure>());
      expect(caught!.statusCode, 429);
    });

    test('400 with gyms → TenantSelectionRequiredFailure', () async {
      final ds = AuthRemoteDataSource(
        FakeDioAdapter.client(
          FakeDioAdapter(
            (_) => FakeDioAdapter.json({
              'detail': 'Specify your gym to continue.',
              'gyms': [
                {'id': 1, 'name': 'Alpha Gym'},
              ],
            }, 400),
          ),
        ),
      );

      await expectLater(
        ds.firebaseLogin(idToken: 't', deviceType: 'web'),
        throwsA(isA<TenantSelectionRequiredFailure>()),
      );
    });

    test('500 → ServerFailure', () async {
      final ds = AuthRemoteDataSource(
        FakeDioAdapter.client(
          FakeDioAdapter((_) => FakeDioAdapter.json({'detail': 'kaput'}, 500)),
        ),
      );

      await expectLater(
        ds.firebaseLogin(idToken: 't', deviceType: 'web'),
        throwsA(isA<ServerFailure>()),
      );
    });

    test('connection error → NetworkFailure', () async {
      final ds = AuthRemoteDataSource(
        FakeDioAdapter.client(
          FakeDioAdapter(
            (options) => throw DioException(
              type: DioExceptionType.connectionError,
              requestOptions: options,
            ),
          ),
        ),
      );

      await expectLater(
        ds.firebaseLogin(idToken: 't', deviceType: 'web'),
        throwsA(isA<NetworkFailure>()),
      );
    });
  });

  group('existing backend-OTP endpoints (rollback path)', () {
    test('requestOtp POSTs phone to /auth/otp/request/', () async {
      await dataSource.requestOtp('+919876543210');

      final request = adapter.requests.single;
      expect(request.uri.path, '/api/v1/auth/otp/request/');
      expect(request.data['phone'], '+919876543210');
    });

    test('verifyOtp POSTs to /auth/otp/verify/ and parses response', () async {
      final response = await dataSource.verifyOtp(
        phone: '+919876543210',
        otp: '123456',
        deviceType: 'android',
        deviceId: 'dev-1',
      );

      final request = adapter.requests.single;
      expect(request.uri.path, '/api/v1/auth/otp/verify/');
      expect(request.data['otp'], '123456');
      expect(response.token, 'session-token-1');
    });

    test('logout tolerates 401 (token already invalid)', () async {
      final ds = AuthRemoteDataSource(
        FakeDioAdapter.client(
          FakeDioAdapter(
            (_) => FakeDioAdapter.json({'detail': 'Invalid'}, 401),
          ),
        ),
      );

      await ds.logout(); // should not throw
    });

    test('getCurrentUser parses profile', () async {
      final response = await dataSource.getCurrentUser();
      expect(response.user.id, 1);
    });
  });
}
