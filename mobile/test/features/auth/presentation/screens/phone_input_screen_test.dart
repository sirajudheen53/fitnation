import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_notifier.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';
import 'package:fitnation_app/features/auth/presentation/providers/firebase_phone_auth_notifier.dart';
import 'package:fitnation_app/router/app_router.dart';

import '../../../../helpers/fakes.dart';

void main() {
  late FakeFirebaseAuthClient firebase;
  late FakeFirebaseAuthRepository repository;
  late ProviderContainer container;

  setUp(() async {
    final local = await setupTestAuthBox();
    firebase = FakeFirebaseAuthClient();
    repository = FakeFirebaseAuthRepository();
    container = ProviderContainer(
      overrides: [
        authLocalDataSourceProvider.overrideWithValue(local),
        firebaseAuthClientProvider.overrideWithValue(firebase),
        firebasePhoneAuthProvider.overrideWith((ref) {
          return FirebasePhoneAuthNotifier(
            firebase,
            repository,
            (response) =>
                ref.read(authProvider.notifier).completeLogin(response),
          );
        }),
      ],
    );
  });

  tearDown(() async {
    container.dispose();
    await teardownTestAuthBox();
  });

  /// Lets the OTP screen's resend-cooldown timer loop finish so no timer is
  /// left pending at teardown.
  Future<void> drainResendCooldown(WidgetTester tester) =>
      tester.pump(const Duration(seconds: 31));

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

  testWidgets('renders brand, phone field and Send OTP button', (tester) async {
    await pumpApp(tester);

    expect(find.text('Welcome to FitNation'), findsOneWidget);
    expect(find.text('Phone Number'), findsOneWidget);
    expect(find.text('Send OTP'), findsOneWidget);
  });

  testWidgets('empty submit shows validation error', (tester) async {
    await pumpApp(tester);

    await tester.tap(find.text('Send OTP'));
    await tester.pump();

    expect(find.text('Please enter your phone number'), findsOneWidget);
    expect(firebase.verifyCalls, isEmpty);
  });

  testWidgets('missing country code shows validation error', (tester) async {
    await pumpApp(tester);

    await tester.enterText(find.byType(TextFormField), '9876543210');
    await tester.tap(find.text('Send OTP'));
    await tester.pump();

    expect(find.text('Include country code (e.g. +91)'), findsOneWidget);
  });

  testWidgets('valid phone sends the code and navigates to the OTP screen', (
    tester,
  ) async {
    firebase.codeSentVerificationId = 'vid-1';
    await pumpApp(tester);

    await tester.enterText(find.byType(TextFormField), '+919876543210');
    await tester.tap(find.text('Send OTP'));
    await tester.pumpAndSettle();

    expect(firebase.verifyCalls, ['+919876543210']);
    expect(find.text('Enter verification code'), findsOneWidget);

    await drainResendCooldown(tester);
  });

  testWidgets('shows friendly error when verification fails', (tester) async {
    firebase.verifyError = const AuthFailure(
      message: "Sign-in isn't set up for this app yet.",
    );
    await pumpApp(tester);

    await tester.enterText(find.byType(TextFormField), '+919876543210');
    await tester.tap(find.text('Send OTP'));
    await tester.pumpAndSettle();

    expect(find.text("Sign-in isn't set up for this app yet."), findsOneWidget);
    expect(find.text('Enter verification code'), findsNothing);
  });

  testWidgets('shows a spinner while the code request is in flight', (
    tester,
  ) async {
    firebase
      ..deferEmission = true
      ..codeSentVerificationId = 'vid';
    await pumpApp(tester);

    await tester.enterText(find.byType(TextFormField), '+919876543210');
    await tester.tap(find.text('Send OTP'));
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsOneWidget);

    // Complete the flow.
    firebase.emitCodeSent('vid');
    await tester.pumpAndSettle();
    expect(find.text('Enter verification code'), findsOneWidget);

    await drainResendCooldown(tester);
  });

  testWidgets('auto-verified sign-in lands on the dashboard', (tester) async {
    firebase.autoVerifiedToken = 'id-token-auto';
    await pumpApp(tester);

    await tester.enterText(find.byType(TextFormField), '+919876543210');
    await tester.tap(find.text('Send OTP'));
    await tester.pumpAndSettle();

    expect(container.read(authProvider).isAuthenticated, isTrue);
    expect(repository.calls.single.idToken, 'id-token-auto');
    // Router redirects the authenticated user to the dashboard.
    expect(find.text('Welcome back,'), findsOneWidget);
  });
}
