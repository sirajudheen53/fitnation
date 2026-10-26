import 'package:firebase_auth/firebase_auth.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/failures.dart';
import '../firebase_error_mapper.dart';

/// Testable seam over [FirebaseAuth] phone-verification flows.
///
/// The app code depends on this interface; unit tests provide a fake so no
/// real Firebase/network/SMS is touched.
abstract class FirebaseAuthClient {
  /// Starts phone verification for [phoneNumber].
  ///
  /// Exactly one of the callbacks fires per attempt (whichever comes first):
  /// - [onCodeSent]: SMS dispatched; [verificationId] is required to later
  ///   [confirmOtp]. On Android, [resendToken] enables forced resend.
  /// - [onAutoVerified]: Android instant/auto-SMS-retrieval verified the
  ///   number on its own — [idToken] is already a valid Firebase ID token.
  /// - [onError]: verification could not start/complete.
  /// - [onCodeAutoRetrievalTimeout]: auto-retrieval gave up; manual code
  ///   entry with the given [verificationId] still works.
  Future<void> verifyPhoneNumber({
    required String phoneNumber,
    required void Function(String verificationId, int? resendToken) onCodeSent,
    required void Function(String idToken) onAutoVerified,
    required void Function(Failure error) onError,
    required void Function(String verificationId) onCodeAutoRetrievalTimeout,
    Duration timeout,
    int? forceResendingToken,
  });

  /// Confirms a user-entered [smsCode] against [verificationId] and returns
  /// the signed-in user's Firebase ID token.
  ///
  /// Throws a [Failure] (mapped from FirebaseAuthException) on failure.
  Future<String> confirmOtp({
    required String verificationId,
    required String smsCode,
  });

  /// Signs out of Firebase (called on app logout).
  Future<void> signOut();
}

/// Production implementation backed by [FirebaseAuth].
class FirebaseAuthClientImpl implements FirebaseAuthClient {
  final FirebaseAuth _firebaseAuth;

  FirebaseAuthClientImpl(this._firebaseAuth);

  @override
  Future<void> verifyPhoneNumber({
    required String phoneNumber,
    required void Function(String verificationId, int? resendToken) onCodeSent,
    required void Function(String idToken) onAutoVerified,
    required void Function(Failure error) onError,
    required void Function(String verificationId) onCodeAutoRetrievalTimeout,
    Duration timeout = AppConstants.phoneVerificationTimeout,
    int? forceResendingToken,
  }) {
    return _firebaseAuth.verifyPhoneNumber(
      phoneNumber: phoneNumber,
      timeout: timeout,
      forceResendingToken: forceResendingToken,
      // Android instant verification / auto-SMS-retrieval: the credential
      // arrives without user input — sign in right away.
      verificationCompleted: (credential) async {
        try {
          onAutoVerified(await _signInAndFetchIdToken(credential));
        } on Failure catch (failure) {
          onError(failure);
        } catch (e) {
          onError(UnknownFailure(message: e.toString()));
        }
      },
      verificationFailed: (e) => onError(mapFirebaseAuthException(e)),
      codeSent: (verificationId, resendToken) =>
          onCodeSent(verificationId, resendToken),
      codeAutoRetrievalTimeout: onCodeAutoRetrievalTimeout,
    );
  }

  @override
  Future<String> confirmOtp({
    required String verificationId,
    required String smsCode,
  }) async {
    try {
      final credential = PhoneAuthProvider.credential(
        verificationId: verificationId,
        smsCode: smsCode,
      );
      return await _signInAndFetchIdToken(credential);
    } on FirebaseAuthException catch (e) {
      throw mapFirebaseAuthException(e);
    }
  }

  @override
  Future<void> signOut() => _firebaseAuth.signOut();

  Future<String> _signInAndFetchIdToken(PhoneAuthCredential credential) async {
    final UserCredential userCredential;
    try {
      userCredential = await _firebaseAuth.signInWithCredential(credential);
    } on FirebaseAuthException catch (e) {
      throw mapFirebaseAuthException(e);
    }
    final user = userCredential.user;
    if (user == null) {
      throw const AuthFailure(message: 'Sign-in failed. Please try again.');
    }
    final idToken = await user.getIdToken();
    if (idToken == null || idToken.isEmpty) {
      throw const AuthFailure(
        message: 'Could not verify your sign-in. Please try again.',
      );
    }
    return idToken;
  }
}
