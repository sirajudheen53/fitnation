import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/failures.dart';
import '../../data/data_sources/firebase_auth_client.dart';
import '../../data/models/auth_response.dart';
import '../../domain/repositories/auth_repository.dart';

/// Lifecycle of the Firebase phone verification + backend session exchange.
enum PhoneAuthStep {
  /// Nothing in progress.
  idle,

  /// Waiting for Firebase to dispatch the SMS (or auto-verify).
  sending,

  /// SMS dispatched — waiting for the user's code.
  codeSent,

  /// Confirming the code with Firebase / exchanging the ID token.
  verifying,

  /// Backend needs the user to specify their gym before completing sign-in.
  gymSelectionRequired,

  /// Verification or sign-in failed (see [FirebasePhoneAuthState.errorMessage]).
  error,
}

/// State of the Firebase phone auth flow.
@immutable
class FirebasePhoneAuthState {
  final PhoneAuthStep step;
  final String? verificationId;
  final int? resendToken;
  final List<GymOption> gyms;
  final String? errorMessage;

  const FirebasePhoneAuthState({
    this.step = PhoneAuthStep.idle,
    this.verificationId,
    this.resendToken,
    this.gyms = const [],
    this.errorMessage,
  });

  FirebasePhoneAuthState copyWith({
    PhoneAuthStep? step,
    String? verificationId,
    int? resendToken,
    List<GymOption>? gyms,
    String? errorMessage,
  }) {
    return FirebasePhoneAuthState(
      step: step ?? this.step,
      verificationId: verificationId ?? this.verificationId,
      resendToken: resendToken ?? this.resendToken,
      gyms: gyms ?? this.gyms,
      errorMessage: errorMessage,
    );
  }

  bool get isLoading =>
      step == PhoneAuthStep.sending || step == PhoneAuthStep.verifying;
}

/// Drives the Firebase phone-OTP login:
/// verifyPhoneNumber → (codeSent | autoVerified) → confirm code →
/// Firebase ID token → POST /auth/firebase/ → session established.
class FirebasePhoneAuthNotifier extends StateNotifier<FirebasePhoneAuthState> {
  final FirebaseAuthClient _client;
  final FirebaseAuthRepository _repository;
  final void Function(AuthResponse response) _onSessionEstablished;

  /// ID token kept after a successful Firebase sign-in so the backend call
  /// can be retried with a gym when the backend asks for disambiguation.
  String? _pendingIdToken;

  FirebasePhoneAuthNotifier(
    this._client,
    this._repository,
    this._onSessionEstablished,
  ) : super(const FirebasePhoneAuthState());

  /// Requests the SMS code for [phone] (also used for resend).
  ///
  /// Resolves `true` once the code has been sent (user should enter it) or
  /// the number was auto-verified and the session established; `false` on
  /// any failure (state carries the friendly error).
  Future<bool> sendCode(String phone) async {
    if (state.isLoading) return false;

    state = state.copyWith(
      step: PhoneAuthStep.sending,
      gyms: const [],
      errorMessage: null,
    );

    final outcome = Completer<bool>();

    await _client.verifyPhoneNumber(
      phoneNumber: phone,
      forceResendingToken: state.resendToken,
      onCodeSent: (verificationId, resendToken) {
        state = state.copyWith(
          step: PhoneAuthStep.codeSent,
          verificationId: verificationId,
          resendToken: resendToken,
          errorMessage: null,
        );
        if (!outcome.isCompleted) outcome.complete(true);
      },
      onAutoVerified: (idToken) async {
        if (!outcome.isCompleted) {
          outcome.complete(await _loginToBackend(idToken));
        }
      },
      onError: (failure) {
        state = state.copyWith(
          step: PhoneAuthStep.error,
          errorMessage: failure.message,
        );
        if (!outcome.isCompleted) outcome.complete(false);
      },
      onCodeAutoRetrievalTimeout: (verificationId) {
        // Keep the verificationId so manual code entry still works.
        state = state.copyWith(verificationId: verificationId);
      },
    );

    return outcome.future;
  }

  /// Confirms the user-entered [code] and completes sign-in.
  Future<bool> verifyCode(String code) async {
    final verificationId = state.verificationId;
    if (verificationId == null) {
      state = state.copyWith(
        step: PhoneAuthStep.error,
        errorMessage: 'No verification in progress. Please request a new code.',
      );
      return false;
    }

    state = state.copyWith(step: PhoneAuthStep.verifying, errorMessage: null);

    try {
      final idToken = await _client.confirmOtp(
        verificationId: verificationId,
        smsCode: code,
      );
      return await _loginToBackend(idToken);
    } on Failure catch (failure) {
      state = state.copyWith(
        step: PhoneAuthStep.error,
        errorMessage: failure.message,
      );
      return false;
    }
  }

  /// Retries the backend session exchange with the selected [gymId] after a
  /// tenant-disambiguation response.
  Future<bool> confirmGym(String gymId) async {
    final idToken = _pendingIdToken;
    if (idToken == null) {
      state = state.copyWith(
        step: PhoneAuthStep.error,
        errorMessage: 'Your sign-in session expired. Please start again.',
      );
      return false;
    }

    state = state.copyWith(step: PhoneAuthStep.verifying, errorMessage: null);
    return _loginToBackend(idToken, gym: gymId);
  }

  /// Clears the error message (keeps the flow state).
  void clearError() {
    if (state.errorMessage == null) return;
    state = state.copyWith(errorMessage: null);
  }

  Future<bool> _loginToBackend(String idToken, {String? gym}) async {
    // Keep the token for a gym-disambiguation retry (cleared on success).
    _pendingIdToken = idToken;
    final result = await _repository.loginWithFirebaseIdToken(
      idToken,
      gym: gym,
    );

    final error = result.error;
    if (error == null) {
      _pendingIdToken = null;
      state = const FirebasePhoneAuthState(step: PhoneAuthStep.idle);
      _onSessionEstablished(result.response!);
      return true;
    }

    if (error is TenantSelectionRequiredFailure) {
      state = state.copyWith(
        step: PhoneAuthStep.gymSelectionRequired,
        gyms: error.gyms,
        errorMessage: null,
      );
      return false;
    }

    state = state.copyWith(
      step: PhoneAuthStep.error,
      errorMessage: error.message,
    );
    return false;
  }
}
