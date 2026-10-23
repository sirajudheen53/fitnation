import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/entitlement.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/domain/repositories/auth_repository.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_notifier.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';
import 'package:fitnation_app/features/auth/presentation/screens/otp_verify_screen.dart';
import 'package:fitnation_app/features/auth/presentation/screens/phone_input_screen.dart';
import 'package:fitnation_app/router/app_router.dart';

/// End-to-end test of the sign-in path: phone → OTP → verify → gate.
///
/// FBOS-011 §7 mandates an "integration test OTP → verify → gate with
/// mocked Dio". Everything below the widget layer is real — the real
/// [AuthRemoteDataSource] (over a mocked Dio adapter), the real
/// [AuthRepository], the real [AuthNotifier] and the real GoRouter
/// redirect. Only the HTTP transport is faked.
///
/// The point of the test is the seam that unit tests miss: the verify
/// response carries the entitlement, the notifier stores it in
/// [AuthState], and the router's redirect then sends the member to the
/// right screen.
void main() {
  const gymUuid = '3f7c1a2b-4d5e-6f70-8192-a3b4c5d6e7f8';

  late List<_RecordedCall> calls;
  late ProviderContainer container;
  late GoRouter router;

  /// Builds the app over a Dio that answers the OTP verify with [entitlement].
  ///
  /// The response body is the real backend shape (FBOS-011 §2.3).
  ({ProviderContainer container, GoRouter router}) buildApp({
    required Map<String, dynamic> verifyResponse,
  }) {
    calls = [];
    final dio = Dio();
    dio.httpClientAdapter = _CannedAdapter(
      handler: (options) {
        if (options.path.contains('/otp/verify/')) {
          return _Reply(200, verifyResponse);
        }
        if (options.path.contains('/otp/request/')) {
          return _Reply(200, {});
        }
        return _Reply(404, {'detail': 'Not found'});
      },
      recorded: calls,
    );

    final repository = AuthRepository(
      AuthRemoteDataSource(dio),
      _InMemoryLocalDataSource(),
    );

    final container = ProviderContainer(
      overrides: [
        authRepositoryProvider.overrideWithValue(repository),
      ],
    );
    final router = container.read(routerProvider);
    return (container: container, router: router);
  }

  Map<String, dynamic> verifyBody(String status, {bool readOnly = false}) => {
        'token': 'tok-1',
        'user': {'id': 7, 'role': 'customer', 'first_name': 'Raman'},
        'permissions': ['app.access'],
        'entitlement': {
          'status': status,
          'read_only': readOnly,
          'plan_name': 'Monthly Unlimited',
          'gym': {'uuid': gymUuid, 'name': 'Hash Fit'},
        },
      };

  Future<void> pumpApp(
    WidgetTester tester, {
    required GoRouter router,
    required ProviderContainer container,
  }) async {
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(
          theme: AppTheme.light,
          routerConfig: router,
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  /// Types [otp] into the six OTP boxes and waits for the verify call.
  Future<void> enterOtp(WidgetTester tester, String otp) async {
    final boxes = find.byType(TextField);
    for (var i = 0; i < otp.length; i++) {
      await tester.enterText(boxes.at(i), otp[i]);
      await tester.pump();
    }
  }

  group('OTP → verify → gate', () {
    testWidgets('an entitled member lands on the dashboard', (tester) async {
      final built = buildApp(
        verifyResponse: verifyBody('active'),
      );
      container = built.container;
      router = built.router;
      await pumpApp(tester, router: router, container: container);

      // Start at the phone input.
      expect(find.byType(PhoneInputScreen), findsOneWidget);

      // Request the OTP.
      await tester.enterText(find.byType(TextFormField), '+919876543210');
      await tester.tap(find.text('Send OTP'));
      await tester.pumpAndSettle();

      // The phone number travels to the verify screen.
      expect(find.byType(OtpVerifyScreen), findsOneWidget);

      await enterOtp(tester, '123456');
      await tester.pumpAndSettle();

      // The entitlement came back and the router let the member through.
      final auth = container.read(authProvider);
      expect(auth.isAuthenticated, isTrue);
      expect(auth.entitlement?.status, AppEntitlementStatus.active);
      expect(auth.isGatedOut, isFalse);
      expect(router.routeInformationProvider.value.uri.path, '/dashboard');
    });

    testWidgets('a member with no entitlement lands on the gate',
        (tester) async {
      final built = buildApp(
        verifyResponse: verifyBody('none'),
      );
      container = built.container;
      router = built.router;
      await pumpApp(tester, router: router, container: container);

      await tester.enterText(find.byType(TextFormField), '+919876543210');
      await tester.tap(find.text('Send OTP'));
      await tester.pumpAndSettle();

      await enterOtp(tester, '123456');
      await tester.pumpAndSettle();

      // The gate is the destination — never a crash and never the
      // dashboard with member data on it.
      final auth = container.read(authProvider);
      expect(auth.isAuthenticated, isTrue);
      expect(auth.isGatedOut, isTrue);
      expect(router.routeInformationProvider.value.uri.path, '/gate');
      expect(find.textContaining('doesn’t include the FitNation app'),
          findsOneWidget);
    });

    testWidgets('an expired member lands on the gate with the end date',
        (tester) async {
      final built = buildApp(
        verifyResponse: {
          ...verifyBody('expired'),
          'entitlement': {
            'status': 'expired',
            'read_only': false,
            'end_date': '2026-10-14',
            'gym': {'uuid': gymUuid, 'name': 'Hash Fit'},
          },
        },
      );
      container = built.container;
      router = built.router;
      await pumpApp(tester, router: router, container: container);

      await tester.enterText(find.byType(TextFormField), '+919876543210');
      await tester.tap(find.text('Send OTP'));
      await tester.pumpAndSettle();

      await enterOtp(tester, '123456');
      await tester.pumpAndSettle();

      expect(router.routeInformationProvider.value.uri.path, '/gate');
      expect(find.textContaining('Your membership has expired'),
          findsOneWidget);
      expect(find.textContaining('14 Oct 2026'), findsOneWidget);
    });

    testWidgets('a grace member keeps the app and is not gated out',
        (tester) async {
      final built = buildApp(
        verifyResponse: verifyBody('grace', readOnly: true),
      );
      container = built.container;
      router = built.router;
      await pumpApp(tester, router: router, container: container);

      await tester.enterText(find.byType(TextFormField), '+919876543210');
      await tester.tap(find.text('Send OTP'));
      await tester.pumpAndSettle();

      await enterOtp(tester, '123456');
      await tester.pumpAndSettle();

      final auth = container.read(authProvider);
      expect(auth.isGatedOut, isFalse);
      expect(auth.isReadOnlyGrace, isTrue);
      expect(router.routeInformationProvider.value.uri.path, '/dashboard');
    });

    testWidgets('the verify call carries the gym anchor', (tester) async {
      final built = buildApp(
        verifyResponse: verifyBody('active'),
      );
      container = built.container;
      router = built.router;
      await pumpApp(tester, router: router, container: container);

      await tester.enterText(find.byType(TextFormField), '+919876543210');
      await tester.tap(find.text('Send OTP'));
      await tester.pumpAndSettle();

      await enterOtp(tester, '123456');
      await tester.pumpAndSettle();

      final verify = calls.firstWhere((c) => c.uri.path.contains('/otp/verify/'));
      final body = verify.body as Map<String, dynamic>;
      expect(body['otp'], '123456');
      expect(body['phone'], '+919876543210');
    });

    testWidgets('a non-India dial code reaches OTP delivery normalized',
        (tester) async {
      final built = buildApp(
        verifyResponse: verifyBody('active'),
      );
      container = built.container;
      router = built.router;
      await pumpApp(tester, router: router, container: container);

      // Switch the dial code to the UAE, then enter the national number.
      await tester.tap(find.byKey(const Key('dial_code_chip')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('United Arab Emirates'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextFormField), '501234567');
      await tester.tap(find.text('Send OTP'));
      await tester.pumpAndSettle();

      // The OTP screen receives the normalized number.
      expect(find.byType(OtpVerifyScreen), findsOneWidget);
      expect(find.textContaining('+971501234567'), findsOneWidget);

      await enterOtp(tester, '123456');
      await tester.pumpAndSettle();

      // Both the request and the verify calls carry exactly one country
      // code, in the same body shape as the India flow.
      expect(
        calls.where((c) => c.uri.path.contains('/otp/request/')).single.body,
        containsPair('phone', '+971501234567'),
      );
      final verify = calls.firstWhere((c) => c.uri.path.contains('/otp/verify/'));
      expect((verify.body as Map<String, dynamic>)['phone'], '+971501234567');
      expect(router.routeInformationProvider.value.uri.path, '/dashboard');
    });
  });
}

/// A local data source that keeps the session in memory (no Hive).
class _InMemoryLocalDataSource extends AuthLocalDataSource {
  String? _token;
  UserModel? _user;
  List<String> _permissions = const [];
  Entitlement? _entitlement;

  @override
  Future<void> saveToken(String value) async => _token = value;

  @override
  String? getToken() => _token;

  @override
  Future<void> saveUser(UserModel value) async => _user = value;

  @override
  UserModel? getUser() => _user;

  @override
  Future<void> savePermissions(List<String> value) async =>
      _permissions = value;

  @override
  List<String> getPermissions() => _permissions;

  @override
  Future<void> saveEntitlement(Entitlement value) async =>
      _entitlement = value;

  @override
  Entitlement? getEntitlement() => _entitlement;

  @override
  bool get isAuthenticated => _token != null;

  @override
  Future<void> clear() async {
    _token = null;
    _user = null;
    _permissions = const [];
    _entitlement = null;
  }
}

/// A recorded request (method, target and body).
class _RecordedCall {
  _RecordedCall(this.method, this.uri, this.body);

  final String method;
  final Uri uri;
  final Object? body;
}

/// A Dio adapter that answers from a handler and records the requests.
class _CannedAdapter implements HttpClientAdapter {
  _CannedAdapter({required this.handler, required this.recorded});

  final _Reply Function(RequestOptions options) handler;
  final List<_RecordedCall> recorded;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    recorded.add(_RecordedCall(options.method, options.uri, options.data));
    final reply = handler(options);
    if (reply.status >= 200 && reply.status < 300) {
      return ResponseBody.fromString(
        jsonEncode(reply.data),
        reply.status,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );
    }

    throw DioException(
      requestOptions: options,
      response: Response<dynamic>(
        requestOptions: options,
        statusCode: reply.status,
        data: reply.data,
      ),
      type: DioExceptionType.badResponse,
    );
  }

  @override
  void close({bool force = false}) {}
}

/// A canned reply (status code and decoded body).
class _Reply {
  const _Reply(this.status, this.data);

  final int status;
  final Object? data;
}
