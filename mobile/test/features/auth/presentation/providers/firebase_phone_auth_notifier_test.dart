import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/auth/data/models/auth_response.dart';
import 'package:fitnation_app/features/auth/presentation/providers/firebase_phone_auth_notifier.dart';

import '../../../../helpers/fakes.dart';

void main() {
  late FakeFirebaseAuthClient client;
  late FakeFirebaseAuthRepository repository;
  AuthResponse? sessionResponse;
  int sessionCallCount = 0;

  FirebasePhoneAuthNotifier buildNotifier() {
    return FirebasePhoneAuthNotifier(client, repository, (response) {
      sessionResponse = response;
      sessionCallCount++;
    });
  }

  setUp(() {
    client = FakeFirebaseAuthClient();
    repository = FakeFirebaseAuthRepository();
    sessionResponse = null;
    sessionCallCount = 0;
  });

  group('sendCode', () {
    test(
      'code sent → step codeSent with verificationId, returns true',
      () async {
        client.codeSentVerificationId = 'vid-42';
        client.codeSentResendToken = 99;
        final notifier = buildNotifier();

        final result = await notifier.sendCode('+919876543210');

        expect(result, isTrue);
        expect(client.verifyCalls, ['+919876543210']);
        expect(notifier.state.step, PhoneAuthStep.codeSent);
        expect(notifier.state.verificationId, 'vid-42');
        expect(notifier.state.resendToken, 99);
        expect(sessionCallCount, 0);
      },
    );

    test('verification failure → error step with friendly message', () async {
      client.verifyError = const AuthFailure(
        message: 'Sign-in is not set up yet.',
      );
      final notifier = buildNotifier();

      final result = await notifier.sendCode('+919876543210');

      expect(result, isFalse);
      expect(notifier.state.step, PhoneAuthStep.error);
      expect(notifier.state.errorMessage, 'Sign-in is not set up yet.');
    });

    test('auto-verified + backend success → session established', () async {
      client.autoVerifiedToken = 'id-token-auto';
      final notifier = buildNotifier();

      final result = await notifier.sendCode('+919876543210');

      expect(result, isTrue);
      expect(sessionCallCount, 1);
      expect(sessionResponse, isA<AuthResponse>());
      expect(repository.calls.single.idToken, 'id-token-auto');
      expect(repository.calls.single.gym, isNull);
      expect(notifier.state.step, PhoneAuthStep.idle);
    });

    test(
      'auto-verified + gym required → gymSelectionRequired with gyms',
      () async {
        client.autoVerifiedToken = 'id-token-auto';
        repository.error = const TenantSelectionRequiredFailure(
          gyms: [
            GymOption(id: '1', name: 'Alpha'),
            GymOption(id: '2', name: 'Beta'),
          ],
        );
        final notifier = buildNotifier();

        final result = await notifier.sendCode('+919876543210');

        expect(result, isFalse);
        expect(notifier.state.step, PhoneAuthStep.gymSelectionRequired);
        expect(notifier.state.gyms.length, 2);
        expect(notifier.state.errorMessage, isNull);
      },
    );

    test('does not fire while a send is already in progress', () async {
      client
        ..deferEmission = true
        ..codeSentVerificationId = 'vid';
      final notifier = buildNotifier();

      final first = notifier.sendCode('+919876543210');
      final second = await notifier.sendCode('+919876543210');

      expect(second, isFalse); // busy → rejected
      expect(client.verifyCalls.length, 1);
      client.emitCodeSent('vid');
      await expectLater(first, completion(isTrue));
    });
  });

  group('verifyCode', () {
    test('confirms with stored verificationId and logs in', () async {
      client.codeSentVerificationId = 'vid-1';
      final notifier = buildNotifier();
      await notifier.sendCode('+919876543210');

      final result = await notifier.verifyCode('123456');

      expect(result, isTrue);
      expect(client.confirmCalls.single.verificationId, 'vid-1');
      expect(client.confirmCalls.single.smsCode, '123456');
      expect(repository.calls.single.idToken, 'id-token-123');
      expect(sessionCallCount, 1);
    });

    test('wrong code → error step with friendly message', () async {
      client.codeSentVerificationId = 'vid-1';
      client.confirmError = const AuthFailure(
        message: 'That code is incorrect.',
      );
      final notifier = buildNotifier();
      await notifier.sendCode('+919876543210');

      final result = await notifier.verifyCode('000000');

      expect(result, isFalse);
      expect(notifier.state.step, PhoneAuthStep.error);
      expect(notifier.state.errorMessage, contains('incorrect'));
    });

    test('without a pending verification → friendly error', () async {
      final notifier = buildNotifier();

      final result = await notifier.verifyCode('123456');

      expect(result, isFalse);
      expect(client.confirmCalls, isEmpty);
      expect(notifier.state.errorMessage, contains('request a new code'));
    });

    test('backend failure after confirm → error surfaced', () async {
      client.codeSentVerificationId = 'vid-1';
      repository.error = const AuthFailure(message: 'Account suspended.');
      final notifier = buildNotifier();
      await notifier.sendCode('+919876543210');

      final result = await notifier.verifyCode('123456');

      expect(result, isFalse);
      expect(notifier.state.errorMessage, 'Account suspended.');
    });
  });

  group('confirmGym', () {
    test('retries backend with selected gym and completes login', () async {
      client.autoVerifiedToken = 'id-token-auto';
      repository.error = const TenantSelectionRequiredFailure(
        message: 'Specify your gym to continue',
        gyms: [GymOption(id: '7', name: 'Alpha Gym')],
      );
      final notifier = buildNotifier();
      await notifier.sendCode('+919876543210');
      expect(notifier.state.step, PhoneAuthStep.gymSelectionRequired);

      final result = await notifier.confirmGym('7');

      expect(result, isTrue);
      expect(repository.calls.last.idToken, 'id-token-auto');
      expect(repository.calls.last.gym, '7');
      expect(sessionCallCount, 1);
    });

    test('without a pending id token → session expired error', () async {
      final notifier = buildNotifier();

      final result = await notifier.confirmGym('7');

      expect(result, isFalse);
      expect(repository.calls, isEmpty);
      expect(notifier.state.errorMessage, contains('expired'));
    });
  });

  test('clearError clears message only', () async {
    client.verifyError = const AuthFailure(message: 'Nope.');
    final notifier = buildNotifier();
    await notifier.sendCode('+919876543210');
    expect(notifier.state.errorMessage, 'Nope.');

    notifier.clearError();

    expect(notifier.state.errorMessage, isNull);
    expect(notifier.state.step, PhoneAuthStep.error);
  });
}
