import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_notifier.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';

import '../../../../helpers/fakes.dart';

void main() {
  late FakeAuthRemoteDataSource remote;
  late FakeFirebaseAuthClient firebase;
  late ProviderContainer container;

  setUp(() async {
    final local = await setupTestAuthBox();
    remote = FakeAuthRemoteDataSource();
    firebase = FakeFirebaseAuthClient();
    container = ProviderContainer(
      overrides: [
        authLocalDataSourceProvider.overrideWithValue(local),
        firebaseAuthClientProvider.overrideWithValue(firebase),
        authRemoteDataSourceProvider.overrideWithValue(remote),
      ],
    );
  });

  tearDown(() async {
    container.dispose();
    await teardownTestAuthBox();
  });

  AuthNotifier getNotifier() => container.read(authProvider.notifier);

  group('init', () {
    test('no stored session → unauthenticated', () async {
      await getNotifier().init();
      expect(getNotifier().state.isUnauthenticated, isTrue);
    });

    test('stored session → authenticated with user and permissions', () async {
      await getNotifier().init();
      final repo = container.read(authRepositoryProvider);
      await repo.loginWithFirebaseIdToken('tok');
      container.read(authProvider.notifier).state = const AuthState(
        status: AuthStatus.unauthenticated,
      );

      await getNotifier().init();

      expect(getNotifier().state.isAuthenticated, isTrue);
      expect(getNotifier().state.user!.id, 1);
      expect(getNotifier().state.permissions, ['workouts.view_workout']);
    });
  });

  group('requestOtp (backend rollback path)', () {
    test('success → returns true', () async {
      expect(await getNotifier().requestOtp('+919876543210'), isTrue);
      expect(getNotifier().state.errorMessage, isNull);
    });

    test('failure → surfaces the friendly message', () async {
      remote.requestOtpError = const AuthFailure(message: 'Nope');

      expect(await getNotifier().requestOtp('+919876543210'), isFalse);
      expect(getNotifier().state.errorMessage, 'Nope');
    });
  });

  group('verifyOtp (backend rollback path)', () {
    test('success → authenticated session', () async {
      final ok = await getNotifier().verifyOtp(
        phone: '+919876543210',
        otp: '123456',
      );

      expect(ok, isTrue);
      expect(getNotifier().state.isAuthenticated, isTrue);
      expect(getNotifier().state.user!.id, 1);
      expect(getNotifier().state.permissions, ['workouts.view_workout']);
    });

    test('failure → error state', () async {
      remote.verifyOtpError = const AuthFailure(message: 'Wrong OTP');

      final ok = await getNotifier().verifyOtp(
        phone: '+919876543210',
        otp: '000000',
      );

      expect(ok, isFalse);
      expect(getNotifier().state.status, AuthStatus.error);
      expect(getNotifier().state.errorMessage, 'Wrong OTP');
    });
  });

  group('logout', () {
    test('clears state', () async {
      await getNotifier().verifyOtp(phone: '+919876543210', otp: '123456');
      expect(getNotifier().state.isAuthenticated, isTrue);

      await getNotifier().logout();

      expect(getNotifier().state.isUnauthenticated, isTrue);
      expect(remote.logoutCalls, ['logout']);
      expect(firebase.signOutCalls, ['sign-out']);
    });
  });

  test('clearError resets the message and status', () async {
    remote.requestOtpError = const AuthFailure(message: 'Nope');
    await getNotifier().requestOtp('+919876543210');
    expect(getNotifier().state.errorMessage, 'Nope');

    getNotifier().clearError();

    expect(getNotifier().state.errorMessage, isNull);
  });
}
