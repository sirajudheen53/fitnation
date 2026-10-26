import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/auth/data/data_sources/api_client.dart';
import 'package:fitnation_app/features/auth/domain/repositories/auth_repository.dart';

import '../../../../helpers/fakes.dart';

void main() {
  late FakeAuthRemoteDataSource remote;
  late FakeFirebaseAuthClient firebase;
  late AuthRepository repository;

  setUp(() async {
    final local = await setupTestAuthBox();
    ApiClient.reset();
    remote = FakeAuthRemoteDataSource();
    firebase = FakeFirebaseAuthClient();
    repository = AuthRepository(remote, local, firebase);
  });

  tearDown(() async {
    await teardownTestAuthBox();
    ApiClient.reset();
  });

  group('loginWithFirebaseIdToken', () {
    test('exchanges token, stores session, configures ApiClient', () async {
      final result = await repository.loginWithFirebaseIdToken('id-token-abc');

      expect(result.error, isNull);
      expect(result.response!.token, 'session-token-1');

      final call = remote.firebaseCalls.single;
      expect(call.idToken, 'id-token-abc');
      expect(call.gym, isNull);
      expect(call.deviceType, isNotEmpty);

      // Session persisted exactly like the OTP flow.
      final session = repository.restoreSession();
      expect(session.token, 'session-token-1');
      expect(session.user!.id, 1);
      expect(
        ApiClient.getInstance().options.headers['Authorization'],
        'Token session-token-1',
      );
    });

    test('passes gym through to the remote data source', () async {
      await repository.loginWithFirebaseIdToken('id-token-abc', gym: '7');
      expect(remote.firebaseCalls.single.gym, '7');
    });

    test('TenantSelectionRequiredFailure surfaced as error', () async {
      remote.firebaseError = const TenantSelectionRequiredFailure(
        gyms: [GymOption(id: '1', name: 'Alpha')],
      );

      final result = await repository.loginWithFirebaseIdToken('tok');

      expect(result.response, isNull);
      expect(result.error, isA<TenantSelectionRequiredFailure>());
      expect(
        (result.error as TenantSelectionRequiredFailure).gyms.single.name,
        'Alpha',
      );
    });

    test('unexpected error → UnknownFailure', () async {
      remote.firebaseError = StateError('boom');
      final result = await repository.loginWithFirebaseIdToken('tok');
      expect(result.error, isA<UnknownFailure>());
    });

    test('implements the FirebaseAuthRepository seam', () {
      expect(repository, isA<FirebaseAuthRepository>());
    });
  });

  group('logout', () {
    test('calls backend, signs out Firebase, clears local session', () async {
      await repository.loginWithFirebaseIdToken('tok');
      expect(firebase.signOutCalls, isEmpty);

      await repository.logout();

      expect(remote.logoutCalls, ['logout']);
      expect(firebase.signOutCalls, ['sign-out']);
      expect(repository.isAuthenticated, isFalse);
      // ApiClient was reset — a fresh instance has no Authorization header.
      expect(
        ApiClient.getInstance().options.headers.containsKey('Authorization'),
        isFalse,
      );
    });

    test('remote logout failure still clears local session', () async {
      await repository.loginWithFirebaseIdToken('tok');
      remote.logoutError = Exception('network down');

      await repository.logout();

      expect(repository.isAuthenticated, isFalse);
    });
  });

  group('restoreSession', () {
    test('restores stored session and configures ApiClient', () async {
      await repository.loginWithFirebaseIdToken('tok');
      ApiClient.reset();

      final session = repository.restoreSession();

      expect(session.token, 'session-token-1');
      expect(session.user!.id, 1);
      expect(session.permissions, ['workouts.view_workout']);
      expect(
        ApiClient.getInstance().options.headers['Authorization'],
        'Token session-token-1',
      );
    });

    test('empty storage → null session', () {
      final session = repository.restoreSession();
      expect(session.token, isNull);
      expect(session.user, isNull);
    });
  });
}
