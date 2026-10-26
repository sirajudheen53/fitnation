import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_auth_platform_interface/firebase_auth_platform_interface.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_core_platform_interface/test.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/auth/data/data_sources/firebase_auth_client.dart';

import '../../../../helpers/fakes.dart';

/// Configurable fake for the FirebaseAuth platform layer.
///
/// The real [FirebaseAuth] Dart API runs against it, exercising
/// [FirebaseAuthClientImpl] end-to-end without the network, SMS or a device.
class _FakeFirebaseAuthPlatform extends FirebaseAuthPlatform {
  // Captured verifyPhoneNumber arguments.
  String? phoneNumber;
  Duration? timeout;
  int? forceResendingToken;
  PhoneVerificationCompleted? verificationCompleted;
  PhoneVerificationFailed? verificationFailed;
  PhoneCodeSent? codeSent;
  PhoneCodeAutoRetrievalTimeout? codeAutoRetrievalTimeout;

  // Captured sign-in / sign-out activity.
  final List<AuthCredential> signInCredentials = [];
  FirebaseAuthException? signInException;
  UserPlatform? signedInUser;
  int signOutCalls = 0;

  _FakeFirebaseAuthPlatform();

  @override
  FirebaseAuthPlatform delegateFor({required FirebaseApp app}) => this;

  @override
  FirebaseAuthPlatform setInitialValues({
    InternalUserDetails? currentUser,
    String? languageCode,
  }) => this;

  @override
  Future<void> verifyPhoneNumber({
    String? phoneNumber,
    PhoneMultiFactorInfo? multiFactorInfo,
    required PhoneVerificationCompleted verificationCompleted,
    required PhoneVerificationFailed verificationFailed,
    required PhoneCodeSent codeSent,
    required PhoneCodeAutoRetrievalTimeout codeAutoRetrievalTimeout,
    Duration timeout = const Duration(seconds: 30),
    int? forceResendingToken,
    MultiFactorSession? multiFactorSession,
    String? autoRetrievedSmsCodeForTesting,
  }) {
    this.phoneNumber = phoneNumber;
    this.timeout = timeout;
    this.forceResendingToken = forceResendingToken;
    this.verificationCompleted = verificationCompleted;
    this.verificationFailed = verificationFailed;
    this.codeSent = codeSent;
    this.codeAutoRetrievalTimeout = codeAutoRetrievalTimeout;
    return Future.value();
  }

  @override
  Future<UserCredentialPlatform> signInWithCredential(
    AuthCredential credential,
  ) async {
    signInCredentials.add(credential);
    final exception = signInException;
    if (exception != null) throw exception;
    return _FakeUserCredentialPlatform(
      auth: this,
      credential: credential,
      user: signedInUser,
    );
  }

  @override
  Future<void> signOut() async {
    signOutCalls++;
  }
}

/// [UserCredentialPlatform] is abstract upstream — subclassing is the
/// intended usage (the platform-interface token check passes via `super`).
class _FakeUserCredentialPlatform extends UserCredentialPlatform {
  _FakeUserCredentialPlatform({
    required super.auth,
    super.credential,
    super.user,
  });
}

class _FakeMultiFactorPlatform extends MultiFactorPlatform {
  _FakeMultiFactorPlatform(super.auth);
}

class _FakeUserPlatform extends UserPlatform {
  final String? idToken;
  bool throwOnGetIdToken = false;

  _FakeUserPlatform(this.idToken, FirebaseAuthPlatform auth)
    : super(
        auth,
        _FakeMultiFactorPlatform(auth),
        InternalUserDetails(
          userInfo: InternalUserInfo(
            uid: 'test-uid',
            isAnonymous: false,
            isEmailVerified: false,
          ),
          providerData: const [],
        ),
      );

  @override
  Future<String?> getIdToken(bool forceRefresh) async {
    if (throwOnGetIdToken) throw StateError('boom');
    return idToken;
  }
}

/// The auto-verified callback chain completes through async continuations;
/// tests flush them with a short real delay before asserting.
Future<void> flushAsync() =>
    Future<void>.delayed(const Duration(milliseconds: 5));

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setupFirebaseCoreMocks();

  var appCounter = 0;
  late _FakeFirebaseAuthPlatform platform;
  late FirebaseAuthClientImpl client;

  // A fresh app per test: FirebaseAuth caches its platform delegate per app
  // name, so this guarantees every test talks to the fake created here.
  Future<FirebaseAuthClientImpl> buildClient() async {
    final index = ++appCounter;
    final app = await Firebase.initializeApp(
      name: 'firebase-auth-client-test-$index',
      options: const FirebaseOptions(
        apiKey: 'test-api-key',
        appId: '1:123456789:android:test',
        messagingSenderId: '123456789',
        projectId: 'yougetfitwithus',
      ),
    );
    final auth = FirebaseAuth.instanceFor(app: app);
    platform = _FakeFirebaseAuthPlatform();
    FirebaseAuthPlatform.instance = platform;
    return FirebaseAuthClientImpl(auth);
  }

  group('verifyPhoneNumber', () {
    test(
      'passes phone, timeout and resend token through, codeSent emits',
      () async {
        client = await buildClient();
        String? verificationId;
        int? resendToken;

        await client.verifyPhoneNumber(
          phoneNumber: '+919876543210',
          onCodeSent: (id, token) {
            verificationId = id;
            resendToken = token;
          },
          onAutoVerified: (_) {},
          onError: (failure) {},
          onCodeAutoRetrievalTimeout: (_) {},
          forceResendingToken: 41,
        );
        platform.codeSent?.call('vid-77', 99);

        expect(platform.phoneNumber, '+919876543210');
        // Default comes from AppConstants.phoneVerificationTimeout.
        expect(platform.timeout, const Duration(seconds: 60));
        expect(platform.forceResendingToken, 41);
        expect(verificationId, 'vid-77');
        expect(resendToken, 99);
      },
    );

    test('verificationFailed → onError with mapped friendly Failure', () async {
      client = await buildClient();
      Failure? failure;

      await client.verifyPhoneNumber(
        phoneNumber: '+919876543210',
        onCodeSent: (_, _) {},
        onAutoVerified: (_) {},
        onError: (f) => failure = f,
        onCodeAutoRetrievalTimeout: (_) {},
      );
      platform.verificationFailed?.call(
        FirebaseAuthException(code: 'too-many-requests'),
      );

      expectFailure(failure, AuthFailure, messageContains: 'too many sign-in');
    });

    test('app-not-authorized → friendly setup error', () async {
      client = await buildClient();
      Failure? failure;

      await client.verifyPhoneNumber(
        phoneNumber: '+919876543210',
        onCodeSent: (_, _) {},
        onAutoVerified: (_) {},
        onError: (f) => failure = f,
        onCodeAutoRetrievalTimeout: (_) {},
      );
      platform.verificationFailed?.call(
        FirebaseAuthException(code: 'app-not-authorized'),
      );

      expectFailure(
        failure,
        AuthFailure,
        messageContains: 'registered for phone sign-in',
      );
    });

    test(
      'codeAutoRetrievalTimeout → passthrough keeps verificationId',
      () async {
        client = await buildClient();
        String? timedOutId;

        await client.verifyPhoneNumber(
          phoneNumber: '+919876543210',
          onCodeSent: (_, _) {},
          onAutoVerified: (_) {},
          onError: (failure) {},
          onCodeAutoRetrievalTimeout: (id) => timedOutId = id,
        );
        platform.codeAutoRetrievalTimeout?.call('vid-timed-out');

        expect(timedOutId, 'vid-timed-out');
      },
    );

    test(
      'verificationCompleted (auto-verify) → id token via onAutoVerified',
      () async {
        client = await buildClient();
        platform.signedInUser = _FakeUserPlatform('id-token-auto', platform);
        String? autoToken;

        await client.verifyPhoneNumber(
          phoneNumber: '+919876543210',
          onCodeSent: (_, _) {},
          onAutoVerified: (token) => autoToken = token,
          onError: (failure) {},
          onCodeAutoRetrievalTimeout: (_) {},
        );
        platform.verificationCompleted?.call(
          PhoneAuthProvider.credential(
            verificationId: 'vid',
            smsCode: '123456',
          ),
        );
        await flushAsync();

        expect(autoToken, 'id-token-auto');
        expect(platform.signInCredentials, hasLength(1));
      },
    );

    test(
      'auto-verify sign-in failure (FirebaseAuthException) → onError',
      () async {
        client = await buildClient();
        platform.signInException = FirebaseAuthException(code: 'user-disabled');
        Failure? failure;

        await client.verifyPhoneNumber(
          phoneNumber: '+919876543210',
          onCodeSent: (_, _) {},
          onAutoVerified: (_) {},
          onError: (f) => failure = f,
          onCodeAutoRetrievalTimeout: (_) {},
        );
        platform.verificationCompleted?.call(
          PhoneAuthProvider.credential(
            verificationId: 'vid',
            smsCode: '123456',
          ),
        );
        await flushAsync();

        expectFailure(failure, AuthFailure, messageContains: 'disabled');
      },
    );

    test('auto-verify with null user → onError sign-in failure', () async {
      client = await buildClient();
      platform.signedInUser = null;
      Failure? failure;

      await client.verifyPhoneNumber(
        phoneNumber: '+919876543210',
        onCodeSent: (_, _) {},
        onAutoVerified: (_) {},
        onError: (f) => failure = f,
        onCodeAutoRetrievalTimeout: (_) {},
      );
      platform.verificationCompleted?.call(
        PhoneAuthProvider.credential(verificationId: 'vid', smsCode: '123456'),
      );
      await flushAsync();

      expectFailure(failure, AuthFailure, messageContains: 'Sign-in failed');
    });

    test('auto-verify with null id token → onError could-not-verify', () async {
      client = await buildClient();
      platform.signedInUser = _FakeUserPlatform(null, platform);
      Failure? failure;

      await client.verifyPhoneNumber(
        phoneNumber: '+919876543210',
        onCodeSent: (_, _) {},
        onAutoVerified: (_) {},
        onError: (f) => failure = f,
        onCodeAutoRetrievalTimeout: (_) {},
      );
      platform.verificationCompleted?.call(
        PhoneAuthProvider.credential(verificationId: 'vid', smsCode: '123456'),
      );
      await flushAsync();

      expectFailure(
        failure,
        AuthFailure,
        messageContains: 'Could not verify your sign-in',
      );
    });

    test('auto-verify unexpected error → onError UnknownFailure', () async {
      client = await buildClient();
      // Force an unexpected (non-FirebaseAuth) error out of sign-in.
      platform.signedInUser = _FakeUserPlatform('unused', platform)
        ..throwOnGetIdToken = true;
      Failure? failure;

      await client.verifyPhoneNumber(
        phoneNumber: '+919876543210',
        onCodeSent: (_, _) {},
        onAutoVerified: (_) {},
        onError: (f) => failure = f,
        onCodeAutoRetrievalTimeout: (_) {},
      );
      platform.verificationCompleted?.call(
        PhoneAuthProvider.credential(verificationId: 'vid', smsCode: '123456'),
      );
      await flushAsync();

      expect(failure, isA<UnknownFailure>());
    });
  });

  group('confirmOtp', () {
    test(
      'builds PhoneAuthCredential, signs in and returns the id token',
      () async {
        client = await buildClient();
        platform.signedInUser = _FakeUserPlatform('id-token-9', platform);

        final token = await client.confirmOtp(
          verificationId: 'vid-9',
          smsCode: '654321',
        );

        expect(token, 'id-token-9');
        final credential =
            platform.signInCredentials.single as PhoneAuthCredential;
        expect(credential.verificationId, 'vid-9');
        expect(credential.smsCode, '654321');
      },
    );

    test(
      'FirebaseAuthException during sign-in → throws mapped Failure',
      () async {
        client = await buildClient();
        platform.signInException = FirebaseAuthException(
          code: 'invalid-verification-code',
        );

        await expectLater(
          client.confirmOtp(verificationId: 'vid', smsCode: '000000'),
          throwsA(
            isA<AuthFailure>().having(
              (f) => f.message,
              'message',
              contains('code is incorrect'),
            ),
          ),
        );
      },
    );
  });

  group('signOut', () {
    test('delegates to FirebaseAuth.signOut', () async {
      client = await buildClient();

      await client.signOut();

      expect(platform.signOutCalls, 1);
    });
  });
}
