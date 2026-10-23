import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/core/preferences/dial_code_providers.dart';
import 'package:fitnation_app/core/preferences/dial_code_store.dart';
import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/core/utils/country_code.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';
import 'package:fitnation_app/features/auth/domain/repositories/auth_repository.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';
import 'package:fitnation_app/features/auth/presentation/providers/dial_code_provider.dart';
import 'package:fitnation_app/features/auth/presentation/screens/phone_input_screen.dart';

/// In-memory dial-code store. A real Hive box must stay out of widget
/// tests: its internal timers never settle under FakeAsync, so
/// pumpAndSettle spins forever (the plain-test suite
/// `dial_code_store_test.dart` covers the real Hive round-trip).
class _InMemoryDialCodeStore extends DialCodeStore {
  CountryCode? _saved;

  @override
  CountryCode? load() => _saved;

  @override
  Future<void> save(CountryCode country) async => _saved = country;
}

/// Repository fake that records requested phone numbers instead of hitting
/// the network — lets widget tests assert the exact wire payload.
class _RecordingAuthRepository extends AuthRepository {
  _RecordingAuthRepository()
      : super(
          AuthRemoteDataSource(Dio()),
          AuthLocalDataSource(),
        );

  final List<String> requestedPhones = [];

  @override
  Future<({Failure? error})> requestOtp(String phone, {String? gymAnchor}) async {
    requestedPhones.add(phone);
    return (error: null);
  }
}

GoRouter _router() => GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(path: '/', builder: (_, _) => const PhoneInputScreen()),
        GoRoute(
          path: '/otp',
          builder: (_, _) => const Scaffold(body: Text('OTP SCREEN')),
        ),
      ],
    );

Future<void> _pumpScreen(
  WidgetTester tester, {
  required ProviderContainer container,
  required GoRouter router,
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

/// Selects [countryName] from the dial-code picker.
Future<void> _pickCountry(WidgetTester tester, String countryName) async {
  await tester.tap(find.byKey(const Key('dial_code_chip')));
  await tester.pumpAndSettle();
  await tester.tap(find.text(countryName));
  await tester.pumpAndSettle();
}

void main() {
  group('PhoneInputScreen dial-code picker', () {
    testWidgets('defaults to India +91 with the 10-digit hint',
        (tester) async {
      await _pumpScreen(
        tester,
        container: ProviderContainer(
          overrides: [
            authRepositoryProvider
                .overrideWithValue(_RecordingAuthRepository()),
          ],
        ),
        router: _router(),
      );

      expect(find.text('+91'), findsOneWidget);
      expect(find.byIcon(Icons.keyboard_arrow_down), findsOneWidget);
      // The field expects the national number now, not "+919876543210".
      expect(find.text('10-digit number'), findsOneWidget);
    });

    testWidgets('picking a country swaps the chip, hint, and validation',
        (tester) async {
      final repo = _RecordingAuthRepository();
      await _pumpScreen(
        tester,
        container: ProviderContainer(
          overrides: [authRepositoryProvider.overrideWithValue(repo)],
        ),
        router: _router(),
      );

      // An 8-digit number is too short for India.
      await tester.enterText(find.byType(TextFormField), '50123456');
      await tester.tap(find.text('Send OTP'));
      await tester.pumpAndSettle();
      expect(find.text('India numbers are 10 digits'), findsOneWidget);

      // Switch to the UAE: same text, now valid, and the hint follows.
      await _pickCountry(tester, 'United Arab Emirates');
      expect(find.text('+971'), findsOneWidget);
      expect(find.text('7–9 digit number'), findsOneWidget);
      expect(find.text('India numbers are 10 digits'), findsNothing);

      // Submitting normalizes to +<dial><national> with one country code.
      await tester.tap(find.text('Send OTP'));
      await tester.pumpAndSettle();
      expect(repo.requestedPhones, ['+97150123456']);
      expect(find.text('OTP SCREEN'), findsOneWidget);
    });

    testWidgets('pasted international numbers never double the country code',
        (tester) async {
      final repo = _RecordingAuthRepository();
      await _pumpScreen(
        tester,
        container: ProviderContainer(
          overrides: [authRepositoryProvider.overrideWithValue(repo)],
        ),
        router: _router(),
      );

      await tester.enterText(find.byType(TextFormField), '+919876543210');
      await tester.tap(find.text('Send OTP'));
      await tester.pumpAndSettle();

      expect(repo.requestedPhones, ['+919876543210']);
    });

    testWidgets('the last selection is remembered via the local pref store',
        (tester) async {
      // Session 1: the member switches to the UAE — the pref is written.
      final store = _InMemoryDialCodeStore();
      final container = ProviderContainer(overrides: [
        authRepositoryProvider.overrideWithValue(_RecordingAuthRepository()),
        dialCodeStoreProvider.overrideWithValue(store),
      ]);
      addTearDown(container.dispose);
      await _pumpScreen(tester, container: container, router: _router());
      await _pickCountry(tester, 'United Arab Emirates');
      expect(store.load()?.code, 'AE');

      // Session 2: a pref that already holds the UAE (as after a restart)
      // seeds a fresh container on +971 instead of the +91 default.
      final remembered = _InMemoryDialCodeStore();
      await remembered.save(CountryCodes.findByIso('AE')!);
      final container2 = ProviderContainer(overrides: [
        authRepositoryProvider.overrideWithValue(_RecordingAuthRepository()),
        dialCodeStoreProvider.overrideWithValue(remembered),
      ]);
      addTearDown(container2.dispose);
      expect(container2.read(selectedCountryProvider).code, 'AE');
      expect(container2.read(selectedCountryProvider).displayDialCode, '+971');
    });

    testWidgets('without a store the screen still works on the default',
        (tester) async {
      // Plain container: dialCodeStoreProvider is not overridden, exactly
      // like widget-test / early-boot environments.
      final repo = _RecordingAuthRepository();
      await _pumpScreen(
        tester,
        container:
            ProviderContainer(overrides: [
              authRepositoryProvider.overrideWithValue(repo),
            ]),
        router: _router(),
      );

      expect(find.text('+91'), findsOneWidget);
      await tester.enterText(find.byType(TextFormField), '9876543210');
      await tester.tap(find.text('Send OTP'));
      await tester.pumpAndSettle();
      expect(repo.requestedPhones, ['+919876543210']);
    });
  });
}
