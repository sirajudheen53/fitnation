import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/constants/app_constants.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';
import 'package:fitnation_app/features/auth/presentation/screens/otp_verify_screen.dart';
import 'package:fitnation_app/features/auth/presentation/screens/phone_input_screen.dart';
import 'package:fitnation_app/router/app_router.dart';

import '../../../../helpers/fakes.dart';

/// Remote data source that appends to a shared timeline so tests can assert
/// the handshake happens before the backend OTP request.
class _TimelineRemoteDataSource extends FakeAuthRemoteDataSource {
  _TimelineRemoteDataSource(this.timeline);

  final List<String> timeline;

  @override
  Future<void> requestOtp(String phone) async {
    timeline.add('requestOtp');
    return super.requestOtp(phone);
  }
}

void main() {
  const methodChannel = MethodChannel('com.getfitwithus.app/whatsapp_otp');

  late _TimelineRemoteDataSource remote;
  late List<String> timeline;
  late ProviderContainer container;

  setUp(() async {
    // These tests exercise the backend-OTP branch (the branch the zero-tap
    // handshake is wired into) without recompiling with a dart-define.
    AppConstants.debugAuthModeOverride = AuthMode.backendOtp;
    final local = await setupTestAuthBox();
    timeline = <String>[];
    remote = _TimelineRemoteDataSource(timeline);
    container = ProviderContainer(
      overrides: [
        authLocalDataSourceProvider.overrideWithValue(local),
        authRemoteDataSourceProvider.overrideWithValue(remote),
        // The provider graph touches FirebaseAuth even in backend mode;
        // keep it faked like the other widget tests do.
        firebaseAuthClientProvider.overrideWithValue(FakeFirebaseAuthClient()),
      ],
    );
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(methodChannel, (call) async {
      if (call.method == 'startHandshake') timeline.add('handshake');
      return call.method == 'startHandshake' ? {'supported': true} : null;
    });
  });

  tearDown(() async {
    AppConstants.debugAuthModeOverride = null;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(methodChannel, null);
    container.dispose();
    await teardownTestAuthBox();
  });

  Future<void> pumpApp(WidgetTester tester) async {
    tester.view.physicalSize = const Size(412, 1000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: Consumer(
          builder: (context, ref, _) {
            // Mirrors FitNationApp: rebuild the router when auth state changes.
            return MaterialApp.router(routerConfig: ref.watch(routerProvider));
          },
        ),
      ),
    );
    await tester.pump();
  }

  /// Lets the OTP screen's resend-cooldown timer loop finish so no timer is
  /// left pending at teardown.
  Future<void> drainResendCooldown(WidgetTester tester) =>
      tester.pump(const Duration(seconds: 31));

  testWidgets(
    'backend OTP request starts the WhatsApp handshake before the request',
    (tester) async {
      await pumpApp(tester);
      expect(find.byType(PhoneInputScreen), findsOneWidget);

      await tester.enterText(find.byType(TextFormField), '+919876543210');
      await tester.tap(find.text('Send OTP'));
      await tester.pumpAndSettle();

      expect(timeline, ['handshake', 'requestOtp']);
      expect(remote.requestOtpCalls, ['+919876543210']);
      expect(find.byType(OtpVerifyScreen), findsOneWidget);

      await drainResendCooldown(tester);
    },
  );

  testWidgets(
    'resending a backend OTP re-starts the handshake before the request',
    (tester) async {
      await pumpApp(tester);
      container.read(routerProvider).go('/otp', extra: '+919876543210');
      await tester.pump();
      await tester.pump();

      // Initial cooldown from screen entry must elapse before resending.
      await tester.pump(const Duration(seconds: 31));
      expect(find.text('Resend code'), findsOneWidget);

      await tester.tap(find.text('Resend code'));
      await tester.pump();
      // Settle the resend's async work plus the snackbar/cooldown timers.
      await tester.pump(const Duration(seconds: 31));

      expect(timeline, ['handshake', 'requestOtp']);
      expect(remote.requestOtpCalls, ['+919876543210']);

      await drainResendCooldown(tester);
    },
  );
}
