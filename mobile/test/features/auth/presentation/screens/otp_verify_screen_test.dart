import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_notifier.dart';
import 'package:fitnation_app/features/auth/presentation/providers/firebase_phone_auth_notifier.dart';
import 'package:fitnation_app/features/auth/presentation/screens/otp_verify_screen.dart';
import 'package:fitnation_app/router/app_router.dart';

import '../../../../helpers/fakes.dart';

void main() {
  late FakeFirebaseAuthClient firebase;
  late FakeFirebaseAuthRepository repository;
  late ProviderContainer container;
  late FirebasePhoneAuthNotifier phoneNotifier;

  setUp(() async {
    final local = await setupTestAuthBox();
    firebase = FakeFirebaseAuthClient();
    repository = FakeFirebaseAuthRepository();
    container = ProviderContainer(
      overrides: [
        authLocalDataSourceProvider.overrideWithValue(local),
        firebaseAuthClientProvider.overrideWithValue(firebase),
        firebasePhoneAuthProvider.overrideWith((ref) {
          phoneNotifier = FirebasePhoneAuthNotifier(
            firebase,
            repository,
            (response) =>
                ref.read(authProvider.notifier).completeLogin(response),
          );
          return phoneNotifier;
        }),
      ],
    );
  });

  tearDown(() async {
    container.dispose();
    await teardownTestAuthBox();
  });

  void presetState(FirebasePhoneAuthState state) {
    // The notifier is created lazily on first read; force it now.
    container.read(firebasePhoneAuthProvider.notifier);
    phoneNotifier.state = state;
  }

  Future<void> pumpApp(
    WidgetTester tester, {
    Size surface = const Size(412, 1000),
  }) async {
    tester.view.physicalSize = surface;
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

  Future<void> openOtpScreen(WidgetTester tester) async {
    container.read(routerProvider).go('/otp', extra: '+919876543210');
    // Two pumps: one to process the navigation, one to build the new page.
    await tester.pump();
    await tester.pump();
  }

  /// Lets the resend-cooldown timer loop finish so no timer is left pending.
  Future<void> drainResendCooldown(WidgetTester tester) =>
      tester.pump(const Duration(seconds: 31));

  Future<void> enterOtp(WidgetTester tester, String code) async {
    final boxes = find.descendant(
      of: find.byType(OtpVerifyScreen),
      matching: find.byType(TextFormField),
    );
    for (var i = 0; i < code.length; i++) {
      await tester.enterText(boxes.at(i), code[i]);
      await tester.pump();
    }
  }

  testWidgets('renders the destination phone number', (tester) async {
    presetState(
      const FirebasePhoneAuthState(
        step: PhoneAuthStep.codeSent,
        verificationId: 'vid-1',
      ),
    );
    await pumpApp(tester);
    await openOtpScreen(tester);

    expect(find.text('Enter verification code'), findsOneWidget);
    expect(find.textContaining('We sent a 6-digit code to'), findsOneWidget);

    await drainResendCooldown(tester);
  });

  testWidgets('entering the 6-digit code confirms it and signs in', (
    tester,
  ) async {
    presetState(
      const FirebasePhoneAuthState(
        step: PhoneAuthStep.codeSent,
        verificationId: 'vid-1',
      ),
    );
    await pumpApp(tester);
    await openOtpScreen(tester);

    await enterOtp(tester, '123456');
    await tester.pumpAndSettle();

    expect(firebase.confirmCalls.single.verificationId, 'vid-1');
    expect(firebase.confirmCalls.single.smsCode, '123456');
    expect(repository.calls.single.idToken, 'id-token-123');
    expect(container.read(authProvider).isAuthenticated, isTrue);
    expect(find.text('Welcome back,'), findsOneWidget); // on the dashboard

    await drainResendCooldown(tester);
  });

  testWidgets('wrong code shows the friendly error and clears inputs', (
    tester,
  ) async {
    presetState(
      const FirebasePhoneAuthState(
        step: PhoneAuthStep.codeSent,
        verificationId: 'vid-1',
      ),
    );
    firebase.confirmError = const AuthFailure(
      message: 'That code is incorrect.',
    );
    await pumpApp(tester);
    await openOtpScreen(tester);

    await enterOtp(tester, '111111');
    await tester.pumpAndSettle();

    expect(find.text('That code is incorrect.'), findsOneWidget);
    final otpBoxes = find.descendant(
      of: find.byType(OtpVerifyScreen),
      matching: find.byType(TextFormField),
    );
    for (final element in otpBoxes.evaluate()) {
      final field = element.widget as TextFormField;
      expect(field.controller!.text, isEmpty);
    }
    expect(container.read(authProvider).isAuthenticated, isFalse);

    await drainResendCooldown(tester);
  });

  testWidgets('gym-required state swaps the form for the gym panel', (
    tester,
  ) async {
    presetState(
      const FirebasePhoneAuthState(
        step: PhoneAuthStep.gymSelectionRequired,
        verificationId: 'vid-1',
        gyms: [GymOption(id: '3', name: 'Alpha Gym')],
      ),
    );
    await pumpApp(tester);
    await openOtpScreen(tester);

    expect(find.text('Specify your gym to continue'), findsOneWidget);
    // Code entry is parked while the gym is being picked.
    expect(find.text('Verify & Continue'), findsNothing);
    final resendButton = tester.widget<TextButton>(
      find.ancestor(
        of: find.textContaining('Resend code in'),
        matching: find.byType(TextButton),
      ),
    );
    expect(resendButton.onPressed, isNull);

    await drainResendCooldown(tester);
  });

  testWidgets('gym panel fits on a small viewport without overflow', (
    tester,
  ) async {
    presetState(
      const FirebasePhoneAuthState(
        step: PhoneAuthStep.gymSelectionRequired,
        verificationId: 'vid-1',
        gyms: [GymOption(id: '3', name: 'Alpha Gym')],
      ),
    );
    await pumpApp(tester, surface: const Size(360, 640));
    await openOtpScreen(tester);

    expect(tester.takeException(), isNull);

    await drainResendCooldown(tester);
  });

  testWidgets('confirming a gym retries the backend and signs in', (
    tester,
  ) async {
    // Drive the real flow: auto-verify hits a gym-disambiguation response,
    // then the picked gym completes the login.
    firebase.autoVerifiedToken = 'id-token-auto';
    repository.error = const TenantSelectionRequiredFailure(
      message: 'Specify your gym to continue',
      gyms: [GymOption(id: '3', name: 'Alpha Gym')],
    );
    container.read(firebasePhoneAuthProvider.notifier);
    await phoneNotifier.sendCode('+919876543210');
    expect(phoneNotifier.state.step, PhoneAuthStep.gymSelectionRequired);

    await pumpApp(tester);
    await openOtpScreen(tester);

    await tester.tap(find.text('Select your gym'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Alpha Gym').last);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ElevatedButton, 'Continue'));
    await tester.pumpAndSettle();

    expect(repository.calls.last.gym, '3');
    expect(container.read(authProvider).isAuthenticated, isTrue);
    expect(find.text('Welcome back,'), findsOneWidget); // on the dashboard

    await drainResendCooldown(tester);
  });

  testWidgets('resend requests a new code after the cooldown', (tester) async {
    presetState(
      const FirebasePhoneAuthState(
        step: PhoneAuthStep.codeSent,
        verificationId: 'vid-1',
      ),
    );
    firebase.codeSentVerificationId = 'vid-2';
    await pumpApp(tester);
    await openOtpScreen(tester);

    expect(find.textContaining('Resend code in'), findsOneWidget);

    // Let the cooldown elapse (fake clock).
    await tester.pump(const Duration(seconds: 31));
    expect(find.text('Resend code'), findsOneWidget);

    await tester.tap(find.text('Resend code'));
    await tester.pumpAndSettle();

    expect(firebase.verifyCalls, ['+919876543210']);
    expect(phoneNotifier.state.verificationId, 'vid-2');

    await drainResendCooldown(tester);
  });

  group('WhatsApp zero-tap broadcasts', () {
    // The messenger's handler registry is keyed by channel name, so a
    // MethodChannel with the event channel's name mocks its listen protocol.
    const eventsChannelForMocks = MethodChannel(
      'com.getfitwithus.app/whatsapp_otp/events',
    );

    void mockEventsChannel() {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(eventsChannelForMocks, (call) async => null);
      addTearDown(
        () => TestDefaultBinaryMessengerBinding
            .instance.defaultBinaryMessenger
            .setMockMethodCallHandler(eventsChannelForMocks, null),
      );
    }

    /// Simulates WhatsApp delivering a zero-tap code broadcast.
    Future<void> pushZeroTapCode(WidgetTester tester, Object? event) async {
      await TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .handlePlatformMessage(
            eventsChannelForMocks.name,
            const StandardMethodCodec().encodeSuccessEnvelope(event),
            (ByteData? data) {},
          );
      await tester.pump();
    }

    testWidgets('a code broadcast auto-fills the boxes and signs in', (
      tester,
    ) async {
      presetState(
        const FirebasePhoneAuthState(
          step: PhoneAuthStep.codeSent,
          verificationId: 'vid-1',
        ),
      );
      mockEventsChannel();
      await pumpApp(tester);
      await openOtpScreen(tester);

      await pushZeroTapCode(tester, '987654');
      await tester.pumpAndSettle();

      expect(firebase.confirmCalls.single.smsCode, '987654');
      expect(container.read(authProvider).isAuthenticated, isTrue);
      expect(find.text('Welcome back,'), findsOneWidget); // on the dashboard

      await drainResendCooldown(tester);
    });

    testWidgets('a payload without 6 digits is ignored (manual entry)', (
      tester,
    ) async {
      presetState(
        const FirebasePhoneAuthState(
          step: PhoneAuthStep.codeSent,
          verificationId: 'vid-1',
        ),
      );
      mockEventsChannel();
      await pumpApp(tester);
      await openOtpScreen(tester);

      await pushZeroTapCode(tester, '12ab45');
      await tester.pumpAndSettle();

      expect(firebase.confirmCalls, isEmpty);
      expect(container.read(authProvider).isAuthenticated, isFalse);
      expect(find.text('Enter verification code'), findsOneWidget);

      await drainResendCooldown(tester);
    });
  });
}
