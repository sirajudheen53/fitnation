import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';
import 'package:fitnation_app/features/auth/data/data_sources/firebase_auth_client.dart';
import 'package:fitnation_app/features/auth/data/models/auth_response.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/domain/repositories/auth_repository.dart';

/// Sample auth payload reused across tests.
AuthResponse buildAuthResponse({int userId = 1}) => AuthResponse(
  token: 'session-token-$userId',
  user: UserModel(
    id: userId,
    email: 'user@test.dev',
    firstName: 'Test',
    lastName: 'User',
    role: 'customer',
    tenantId: 7,
    tenantName: 'Alpha Gym',
  ),
  permissions: const ['workouts.view_workout'],
);

Map<String, dynamic> authResponseJson({int userId = 1}) {
  final response = buildAuthResponse(userId: userId);
  return response.toJson();
}

/// Initializes Hive in a fresh temp directory and returns a ready local data
/// source. Pair with [teardownTestAuthBox].
Future<AuthLocalDataSource> setupTestAuthBox() async {
  final dir = await Directory.systemTemp.createTemp('fitnation_hive_test');
  Hive.init(dir.path);
  final source = AuthLocalDataSource();
  await source.init();
  return source;
}

/// Closes and removes the test auth box and its temp directory.
Future<void> teardownTestAuthBox() async {
  try {
    await Hive.deleteBoxFromDisk('auth_box');
  } catch (_) {}
  try {
    await Hive.close();
  } catch (_) {}
}

/// Configurable fake for [FirebaseAuthClient] — no real Firebase/network/SMS.
class FakeFirebaseAuthClient implements FirebaseAuthClient {
  /// Config for the next [verifyPhoneNumber] call.
  String? codeSentVerificationId;
  int? codeSentResendToken;
  String? autoVerifiedToken;
  Failure? verifyError;

  /// Config for [confirmOtp].
  String confirmToken = 'id-token-123';
  Failure? confirmError;

  /// When true, [verifyPhoneNumber] does not emit anything by itself; tests
  /// drive the captured callbacks manually.
  bool deferEmission = false;

  final List<String> verifyCalls = [];
  final List<String> signOutCalls = [];
  final List<({String verificationId, String smsCode})> confirmCalls = [];

  /// Callbacks captured from the last [verifyPhoneNumber] call.
  void Function(String verificationId, int? resendToken)? onCodeSent;
  void Function(String idToken)? onAutoVerified;
  void Function(Failure error)? onError;
  void Function(String verificationId)? onCodeAutoRetrievalTimeout;

  @override
  Future<void> verifyPhoneNumber({
    required String phoneNumber,
    required void Function(String verificationId, int? resendToken) onCodeSent,
    required void Function(String idToken) onAutoVerified,
    required void Function(Failure error) onError,
    required void Function(String verificationId) onCodeAutoRetrievalTimeout,
    Duration timeout = const Duration(seconds: 60),
    int? forceResendingToken,
  }) async {
    verifyCalls.add(phoneNumber);
    this.onCodeSent = onCodeSent;
    this.onAutoVerified = onAutoVerified;
    this.onError = onError;
    this.onCodeAutoRetrievalTimeout = onCodeAutoRetrievalTimeout;

    if (deferEmission) return;
    if (verifyError != null) {
      onError(verifyError!);
    } else if (autoVerifiedToken != null) {
      onAutoVerified(autoVerifiedToken!);
    } else if (codeSentVerificationId != null) {
      onCodeSent(codeSentVerificationId!, codeSentResendToken);
    }
  }

  /// Simulates Android instant verification / auto-SMS-retrieval.
  void emitAutoVerified(String idToken) => onAutoVerified?.call(idToken);

  /// Simulates the SMS being dispatched.
  void emitCodeSent(String verificationId, {int? resendToken}) =>
      onCodeSent?.call(verificationId, resendToken);

  /// Simulates a verification failure.
  void emitError(Failure failure) => onError?.call(failure);

  @override
  Future<String> confirmOtp({
    required String verificationId,
    required String smsCode,
  }) async {
    confirmCalls.add((verificationId: verificationId, smsCode: smsCode));
    final error = confirmError;
    if (error != null) throw error;
    return confirmToken;
  }

  @override
  Future<void> signOut() async {
    signOutCalls.add('sign-out');
  }
}

/// Fake [FirebaseAuthRepository] recording login calls.
class FakeFirebaseAuthRepository implements FirebaseAuthRepository {
  AuthResponse? response = buildAuthResponse();

  /// Failure returned by the NEXT login call (one-shot) — then cleared, so a
  /// retry succeeds unless reconfigured.
  Failure? error;
  final List<({String idToken, String? gym})> calls = [];

  @override
  Future<({AuthResponse? response, Failure? error})> loginWithFirebaseIdToken(
    String idToken, {
    String? gym,
  }) async {
    calls.add((idToken: idToken, gym: gym));
    final nextError = error;
    error = null;
    return (response: response, error: nextError);
  }
}

/// Fake [AuthRemoteDataSource] for repository tests.
class FakeAuthRemoteDataSource implements AuthRemoteDataSource {
  AuthResponse firebaseResponse = buildAuthResponse();
  Object? firebaseError;
  Object? logoutError;
  Object? requestOtpError;
  Object? verifyOtpError;
  final List<({String idToken, String? gym, String deviceType})> firebaseCalls =
      [];
  final List<String> logoutCalls = [];
  final List<String> requestOtpCalls = [];

  @override
  Future<void> requestOtp(String phone) async {
    requestOtpCalls.add(phone);
    final error = requestOtpError;
    if (error != null) throw error;
  }

  @override
  Future<AuthResponse> firebaseLogin({
    required String idToken,
    required String deviceType,
    String? gym,
  }) async {
    firebaseCalls.add((idToken: idToken, gym: gym, deviceType: deviceType));
    final error = firebaseError;
    if (error != null) throw error;
    return firebaseResponse;
  }

  final List<String> verifyOtpCalls = [];

  @override
  Future<AuthResponse> verifyOtp({
    required String phone,
    required String otp,
    required String deviceType,
    String? deviceId,
    String? userAgent,
  }) async {
    verifyOtpCalls.add(phone);
    final error = verifyOtpError;
    if (error != null) throw error;
    return buildAuthResponse();
  }

  @override
  Future<void> logout() async {
    logoutCalls.add('logout');
    final error = logoutError;
    if (error != null) throw error;
  }

  @override
  Future<AuthResponse> getCurrentUser() async => buildAuthResponse();
}

/// Dio adapter serving canned [ResponseBody]s and recording requests.
class FakeDioAdapter implements HttpClientAdapter {
  final ResponseBody Function(RequestOptions options) handler;
  final List<RequestOptions> requests = [];

  FakeDioAdapter(this.handler);

  /// A Dio instance pointed at the fake adapter.
  static Dio client(FakeDioAdapter adapter) {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local/api/v1'));
    dio.httpClientAdapter = adapter;
    return dio;
  }

  /// JSON response body with the given [status].
  static ResponseBody json(Map<String, dynamic> body, [int status = 200]) =>
      ResponseBody.fromString(
        jsonEncode(body),
        status,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );

  /// JSON array response body with the given [status] (DRF list endpoints).
  static ResponseBody jsonList(List<dynamic> items, [int status = 200]) =>
      ResponseBody.fromString(
        jsonEncode(items),
        status,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    return handler(options);
  }

  @override
  void close({bool force = false}) {}
}

/// Asserts [failure] is of exactly [type] and (optionally) contains text.
void expectFailure(Failure? failure, Type type, {String? messageContains}) {
  expect(failure, isNotNull);
  expect(failure!.runtimeType, type);
  if (messageContains != null) {
    expect(
      failure.message.toLowerCase(),
      contains(messageContains.toLowerCase()),
    );
  }
}
