import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/auth_response.dart';
import 'package:fitnation_app/features/auth/data/models/entitlement.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/domain/repositories/auth_repository.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_notifier.dart';

/// A local data source that records what was written, without Hive.
class _FakeLocalDataSource extends AuthLocalDataSource {
  String? token;
  UserModel? user;
  List<String> permissions = const [];
  Entitlement? entitlement;
  int clearCalls = 0;

  @override
  Future<void> saveToken(String value) async => token = value;

  @override
  String? getToken() => token;

  @override
  Future<void> saveUser(UserModel value) async => user = value;

  @override
  UserModel? getUser() => user;

  @override
  Future<void> savePermissions(List<String> value) async =>
      permissions = value;

  @override
  List<String> getPermissions() => permissions;

  @override
  Future<void> saveEntitlement(Entitlement value) async =>
      entitlement = value;

  @override
  Entitlement? getEntitlement() => entitlement;

  @override
  bool get isAuthenticated => token != null;

  @override
  Future<void> clear() async {
    clearCalls++;
    token = null;
    user = null;
    permissions = const [];
    entitlement = null;
  }
}

/// A remote data source that answers from a script.
class _FakeRemoteDataSource extends AuthRemoteDataSource {
  _FakeRemoteDataSource() : super(Dio());

  Object? requestOtpError;
  Object? verifyOtpError;
  Object? fetchEntitlementError;

  String? requestedAnchor;
  String? verifiedAnchor;

  @override
  Future<void> requestOtp(String phone, {String? gymAnchor}) async {
    requestedAnchor = gymAnchor;
    if (requestOtpError != null) throw requestOtpError!;
  }

  @override
  Future<AuthResponse> verifyOtp({
    required String phone,
    required String otp,
    required String deviceType,
    String? deviceId,
    String? userAgent,
    String? gymAnchor,
  }) async {
    verifiedAnchor = gymAnchor;
    if (verifyOtpError != null) throw verifyOtpError!;
    return AuthResponse(
      token: 'token-1',
      user: const UserModel(id: 7, role: 'customer', firstName: 'Raman'),
      permissions: const ['app.access'],
      entitlement: const Entitlement(status: AppEntitlementStatus.active),
    );
  }

  @override
  Future<AuthResponse> getCurrentUser() async => AuthResponse(
        token: 'token-1',
        user: const UserModel(id: 7, role: 'customer', firstName: 'Raman'),
        permissions: const ['app.access'],
        entitlement: const Entitlement(status: AppEntitlementStatus.active),
      );

  @override
  Future<Entitlement> fetchEntitlement() async {
    if (fetchEntitlementError != null) throw fetchEntitlementError!;
    return const Entitlement(status: AppEntitlementStatus.active);
  }

  @override
  Future<void> logout() async {
    // No server call in the fake.
  }
}

void main() {
  late _FakeRemoteDataSource remote;
  late _FakeLocalDataSource local;
  late AuthRepository repository;

  setUp(() {
    remote = _FakeRemoteDataSource();
    local = _FakeLocalDataSource();
    repository = AuthRepository(remote, local);
  });

  group('init', () {
    test('with no stored session the state is unauthenticated', () async {
      final notifier = AuthNotifier(repository);

      await notifier.init();

      expect(notifier.state.status, AuthStatus.unauthenticated);
      expect(notifier.state.isAuthenticated, isFalse);
    });

    test('with a stored session the state is authenticated', () async {
      await repository.verifyOtp(phone: '+919876543210', otp: '123456');
      final notifier = AuthNotifier(repository);

      await notifier.init();

      expect(notifier.state.status, AuthStatus.authenticated);
      expect(notifier.state.user?.id, 7);
      expect(notifier.state.permissions, ['app.access']);
      expect(notifier.state.entitlement?.status, AppEntitlementStatus.active);
    });
  });

  group('requestOtp', () {
    test('succeeds and clears the error', () async {
      final notifier = AuthNotifier(repository);

      final ok = await notifier.requestOtp('+919876543210');

      expect(ok, isTrue);
      expect(notifier.state.errorMessage, isNull);
      expect(notifier.state.isLoading, isFalse);
    });

    test('a failure sets the error message', () async {
      remote.requestOtpError = const ServerFailure(message: 'no such gym');
      final notifier = AuthNotifier(repository);

      final ok = await notifier.requestOtp('+919876543210');

      expect(ok, isFalse);
      expect(notifier.state.errorMessage, 'no such gym');
      expect(notifier.state.status, AuthStatus.unauthenticated);
    });
  });

  group('verifyOtp', () {
    test('succeeds and stores the session', () async {
      final notifier = AuthNotifier(repository);

      final ok = await notifier.verifyOtp(
        phone: '+919876543210',
        otp: '123456',
      );

      expect(ok, isTrue);
      expect(notifier.state.status, AuthStatus.authenticated);
      expect(notifier.state.entitlement?.status, AppEntitlementStatus.active);
    });

    test('a failure sets the error status', () async {
      remote.verifyOtpError = const AuthFailure(message: 'bad otp');
      final notifier = AuthNotifier(repository);

      final ok = await notifier.verifyOtp(
        phone: '+919876543210',
        otp: '000000',
      );

      expect(ok, isFalse);
      expect(notifier.state.status, AuthStatus.error);
      expect(notifier.state.errorMessage, 'bad otp');
    });
  });

  group('refreshProfile', () {
    test('updates the user, permissions and entitlement', () async {
      final notifier = AuthNotifier(repository);
      await notifier.verifyOtp(phone: '+919876543210', otp: '123456');

      final ok = await notifier.refreshProfile();

      expect(ok, isTrue);
      expect(notifier.state.user?.id, 7);
      expect(notifier.state.entitlement?.status, AppEntitlementStatus.active);
    });
  });

  group('refreshEntitlement', () {
    test('applies the live entitlement', () async {
      final notifier = AuthNotifier(repository);
      await notifier.verifyOtp(phone: '+919876543210', otp: '123456');

      final ok = await notifier.refreshEntitlement();

      expect(ok, isTrue);
      expect(notifier.state.entitlement?.status, AppEntitlementStatus.active);
    });

    test('a network failure keeps the cached entitlement (fail-safe)', () async {
      remote.fetchEntitlementError = const NetworkFailure();
      final notifier = AuthNotifier(repository);
      await notifier.verifyOtp(phone: '+919876543210', otp: '123456');

      final ok = await notifier.refreshEntitlement();

      expect(ok, isFalse);
      // The cached (active) entitlement is still there — a network blip
      // must not gate a paying member out.
      expect(notifier.state.entitlement?.status, AppEntitlementStatus.active);
    });
  });

  group('applyAccessDeniedCode', () {
    test('app_access_required gates the member out', () async {
      final notifier = AuthNotifier(repository);
      await notifier.verifyOtp(phone: '+919876543210', otp: '123456');

      notifier.applyAccessDeniedCode('app_access_required');

      expect(notifier.state.isGatedOut, isTrue);
      expect(notifier.state.entitlement?.status, AppEntitlementStatus.expired);
    });

    test('app_access_read_only puts the member in grace', () async {
      final notifier = AuthNotifier(repository);
      await notifier.verifyOtp(phone: '+919876543210', otp: '123456');

      notifier.applyAccessDeniedCode('app_access_read_only');

      expect(notifier.state.isGatedOut, isFalse);
      expect(notifier.state.isReadOnlyGrace, isTrue);
    });

    test('a code with no cached entitlement still flips the state', () {
      final notifier = AuthNotifier(repository);

      notifier.applyAccessDeniedCode('app_access_required');

      expect(notifier.state.isGatedOut, isTrue);
      expect(notifier.state.entitlement?.status, AppEntitlementStatus.expired);
    });

    test('an unknown code changes nothing', () async {
      final notifier = AuthNotifier(repository);
      await notifier.verifyOtp(phone: '+919876543210', otp: '123456');

      notifier.applyAccessDeniedCode('other');

      expect(notifier.state.isGatedOut, isFalse);
      expect(notifier.state.isReadOnlyGrace, isFalse);
    });
  });

  group('logout', () {
    test('clears the state', () async {
      final notifier = AuthNotifier(repository);
      await notifier.verifyOtp(phone: '+919876543210', otp: '123456');

      await notifier.logout();

      expect(notifier.state.status, AuthStatus.unauthenticated);
      expect(notifier.state.user, isNull);
      expect(local.clearCalls, 1);
    });
  });

  group('clearError', () {
    test('clears the error message and the status', () async {
      final notifier = AuthNotifier(repository);
      await notifier.verifyOtp(phone: '+919876543210', otp: '123456');
      notifier.state = notifier.state.copyWith(errorMessage: 'boom');

      notifier.clearError();

      expect(notifier.state.errorMessage, isNull);
      expect(notifier.state.status, AuthStatus.unauthenticated);
    });
  });

  group('anchor resolution', () {
    test('the resolved anchor is sent with the OTP request', () async {
      final notifier = AuthNotifier(
        repository,
        anchorResolver: () => 'gym-anchor-1',
      );

      await notifier.requestOtp('+919876543210');

      expect(remote.requestedAnchor, 'gym-anchor-1');
    });

    test('an explicit anchor wins over the resolved one', () async {
      final notifier = AuthNotifier(
        repository,
        anchorResolver: () => 'gym-anchor-1',
      );

      await notifier.requestOtp('+919876543210', gymAnchor: 'explicit');

      expect(remote.requestedAnchor, 'explicit');
    });

    test('the resolved anchor is sent with the OTP verify', () async {
      final notifier = AuthNotifier(
        repository,
        anchorResolver: () => 'gym-anchor-1',
      );

      await notifier.verifyOtp(phone: '+919876543210', otp: '123456');

      expect(remote.verifiedAnchor, 'gym-anchor-1');
    });

    test('no resolver means no anchor', () async {
      final notifier = AuthNotifier(repository);

      await notifier.requestOtp('+919876543210');

      expect(remote.requestedAnchor, isNull);
      expect(notifier.effectiveGymAnchor, isNull);
    });
  });
}
