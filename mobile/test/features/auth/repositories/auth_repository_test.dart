import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/auth_response.dart';
import 'package:fitnation_app/features/auth/data/models/entitlement.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/domain/repositories/auth_repository.dart';

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
  Object? getCurrentUserError;
  Object? fetchEntitlementError;
  Object? logoutError;

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
    return _response();
  }

  @override
  Future<AuthResponse> getCurrentUser() async {
    if (getCurrentUserError != null) throw getCurrentUserError!;
    return _response();
  }

  @override
  Future<Entitlement> fetchEntitlement() async {
    if (fetchEntitlementError != null) throw fetchEntitlementError!;
    return const Entitlement(status: AppEntitlementStatus.active);
  }

  @override
  Future<void> logout() async {
    if (logoutError != null) throw logoutError!;
  }

  AuthResponse _response() => AuthResponse(
        token: 'token-1',
        user: const UserModel(id: 7, role: 'customer', firstName: 'Raman'),
        permissions: const ['app.access'],
        entitlement: const Entitlement(status: AppEntitlementStatus.active),
      );
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

  group('requestOtp', () {
    test('passes the gym anchor through', () async {
      final result = await repository.requestOtp('+919876543210',
          gymAnchor: 'gym-uuid');

      expect(result.error, isNull);
      expect(remote.requestedAnchor, 'gym-uuid');
    });

    test('a server failure is returned, not thrown', () async {
      remote.requestOtpError = const ServerFailure(message: 'nope');

      final result = await repository.requestOtp('+919876543210');

      expect(result.error, isA<ServerFailure>());
    });

    test('an unexpected error becomes an UnknownFailure', () async {
      remote.requestOtpError = StateError('boom');

      final result = await repository.requestOtp('+919876543210');

      expect(result.error, isA<UnknownFailure>());
    });
  });

  group('verifyOtp', () {
    test('stores the session and returns the response', () async {
      final result = await repository.verifyOtp(
        phone: '+919876543210',
        otp: '123456',
        gymAnchor: 'gym-uuid',
      );

      expect(result.error, isNull);
      expect(result.response?.token, 'token-1');
      expect(local.token, 'token-1');
      expect(local.user?.id, 7);
      expect(local.permissions, ['app.access']);
      expect(local.entitlement?.status, AppEntitlementStatus.active);
      expect(remote.verifiedAnchor, 'gym-uuid');
    });

    test('a response without a token is an auth failure', () async {
      // A remote that answers without a token.
      final repo = AuthRepository(_TokenlessRemoteDataSource(), local);

      final result = await repo.verifyOtp(
        phone: '+919876543210',
        otp: '123456',
      );

      expect(result.response, isNull);
      expect(result.error, isA<AuthFailure>());
    });

    test('a server failure is returned, not thrown', () async {
      remote.verifyOtpError = const AuthFailure(message: 'bad otp');

      final result = await repository.verifyOtp(
        phone: '+919876543210',
        otp: '000000',
      );

      expect(result.response, isNull);
      expect(result.error, isA<AuthFailure>());
    });
  });

  group('restoreSession', () {
    test('returns nulls when nothing is stored', () {
      final session = repository.restoreSession();

      expect(session.token, isNull);
      expect(session.user, isNull);
      expect(session.permissions, isEmpty);
      expect(session.entitlement, isNull);
    });

    test('returns the stored session and entitlement', () async {
      await repository.verifyOtp(phone: '+919876543210', otp: '123456');

      final session = repository.restoreSession();

      expect(session.token, 'token-1');
      expect(session.user?.id, 7);
      expect(session.entitlement?.status, AppEntitlementStatus.active);
    });
  });

  group('refreshProfile', () {
    test('returns the refreshed user, permissions and entitlement', () async {
      final result = await repository.refreshProfile();

      expect(result.error, isNull);
      expect(result.user?.id, 7);
      expect(result.permissions, ['app.access']);
      expect(result.entitlement?.status, AppEntitlementStatus.active);
    });

    test('a failure is returned, not thrown', () async {
      remote.getCurrentUserError = const ServerFailure(message: 'down');

      final result = await repository.refreshProfile();

      expect(result.error, isA<ServerFailure>());
      expect(result.user, isNull);
    });
  });

  group('fetchEntitlement', () {
    test('returns and stores the live entitlement', () async {
      final result = await repository.fetchEntitlement();

      expect(result.error, isNull);
      expect(result.entitlement?.status, AppEntitlementStatus.active);
      expect(local.entitlement?.status, AppEntitlementStatus.active);
    });

    test('a failure is returned, not thrown', () async {
      remote.fetchEntitlementError = const NetworkFailure();

      final result = await repository.fetchEntitlement();

      expect(result.error, isA<NetworkFailure>());
      expect(result.entitlement, isNull);
    });
  });

  group('logout', () {
    test('clears the local session', () async {
      await repository.verifyOtp(phone: '+919876543210', otp: '123456');

      await repository.logout();

      expect(local.clearCalls, 1);
      expect(local.token, isNull);
    });

    test('the local session is cleared even when the server call fails',
        () async {
      remote.logoutError = const ServerFailure(message: 'down');
      await repository.verifyOtp(phone: '+919876543210', otp: '123456');

      await expectLater(repository.logout(), throwsA(isA<ServerFailure>()));

      expect(local.clearCalls, 1);
    });
  });

  group('accessors', () {
    test('expose the stored session', () async {
      await repository.verifyOtp(phone: '+919876543210', otp: '123456');

      expect(repository.isAuthenticated, isTrue);
      expect(repository.currentUser?.id, 7);
      expect(repository.permissions, ['app.access']);
    });
  });
}

/// A remote data source whose verify response carries no token.
class _TokenlessRemoteDataSource extends AuthRemoteDataSource {
  _TokenlessRemoteDataSource() : super(Dio());

  @override
  Future<AuthResponse> verifyOtp({
    required String phone,
    required String otp,
    required String deviceType,
    String? deviceId,
    String? userAgent,
    String? gymAnchor,
  }) async {
    return AuthResponse(
      user: const UserModel(id: 7, role: 'customer', firstName: 'Raman'),
    );
  }
}
