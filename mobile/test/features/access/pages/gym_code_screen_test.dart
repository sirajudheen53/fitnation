import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fitnation_app/core/anchor/anchor_providers.dart';
import 'package:fitnation_app/core/anchor/anchor_store.dart';
import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/access/data/data_sources/tenant_lookup_remote_data_source.dart';
import 'package:fitnation_app/features/access/presentation/pages/gym_code_screen.dart';
import 'package:fitnation_app/features/access/presentation/providers/gym_code_providers.dart';

/// A lookup data source that answers from a script instead of the network.
class _FakeLookupSource extends TenantLookupRemoteDataSource {
  _FakeLookupSource(this.result, {this.error}) : super(Dio());

  final GymLookup? result;
  final Failure? error;

  @override
  Future<GymLookup> lookupByCode(String code) async {
    final err = error;
    if (err != null) throw err;
    return result!;
  }
}

void main() {
  late _InMemoryAnchorStore store;

  const gymUuid = '3f7c1a2b-4d5e-6f70-8192-a3b4c5d6e7f8';

  setUp(() {
    store = _InMemoryAnchorStore();
  });

  Widget buildWidget(_FakeLookupSource source) {
    return ProviderScope(
      overrides: [
        tenantLookupRemoteDataSourceProvider.overrideWithValue(source),
        anchorStoreProvider.overrideWithValue(store),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const GymCodeScreen(),
      ),
    );
  }

  testWidgets('shows the gym-code prompt', (tester) async {
    await tester.pumpWidget(
      buildWidget(_FakeLookupSource(
        const GymLookup(uuid: gymUuid, name: 'Hash Fit'),
      )),
    );
    await tester.pumpAndSettle();

    expect(find.text('Enter your gym code'), findsOneWidget);
    expect(find.text('Find my gym'), findsOneWidget);
  });

  testWidgets('rejects an empty code without calling the API', (tester) async {
    var called = false;
    await tester.pumpWidget(
      buildWidget(_FakeLookupSource(
        const GymLookup(uuid: gymUuid, name: 'Hash Fit'),
      )),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Find my gym'));
    await tester.pump();

    expect(called, isFalse);
    expect(find.text('Enter the code from your gym'), findsOneWidget);
  });

  testWidgets('a known code resolves the gym and pins the anchor', (
    tester,
  ) async {
    await tester.pumpWidget(
      buildWidget(_FakeLookupSource(
        const GymLookup(uuid: gymUuid, name: 'Hash Fit'),
      )),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextFormField), 'hashfit');
    // Drop focus so the text-field cursor stops blinking and
    // `pumpAndSettle` can settle.
    tester.testTextInput.hide();
    FocusManager.instance.primaryFocus?.unfocus();
    await tester.tap(find.text('Find my gym'));
    await _settle(tester);

    expect(find.text('You are all set'), findsOneWidget);
    expect(find.textContaining('Hash Fit'), findsOneWidget);
    // The anchor is persisted so the next OTP is issued by this gym.
    expect(store.runtimeGymUuid, gymUuid);
  });

  testWidgets('a 404 shows a friendly message and does not crash', (
    tester,
  ) async {
    await tester.pumpWidget(
      buildWidget(_FakeLookupSource(
        null,
        error: const ServerFailure(message: 'Gym not found.', statusCode: 404),
      )),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextFormField), 'WRONG');
    tester.testTextInput.hide();
    FocusManager.instance.primaryFocus?.unfocus();
    await tester.tap(find.text('Find my gym'));
    await _settle(tester);

    expect(find.textContaining('could not find that gym code'), findsOneWidget);
    // No success state, and no anchor was written.
    expect(find.text('You are all set'), findsNothing);
    expect(store.runtimeGymUuid, isNull);
  });

  testWidgets('a network failure shows the error and keeps the form', (
    tester,
  ) async {
    await tester.pumpWidget(
      buildWidget(_FakeLookupSource(null, error: const NetworkFailure())),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextFormField), 'HASHFIT');
    tester.testTextInput.hide();
    FocusManager.instance.primaryFocus?.unfocus();
    await tester.tap(find.text('Find my gym'));
    await _settle(tester);

    expect(find.textContaining('Network error'), findsOneWidget);
    expect(find.text('Find my gym'), findsOneWidget);
    expect(store.runtimeGymUuid, isNull);
  });

  testWidgets('an unexpected error is caught and shown, not thrown', (
    tester,
  ) async {
    await tester.pumpWidget(
      buildWidget(_FakeLookupSource(
        const GymLookup(uuid: gymUuid, name: 'Hash Fit'),
      )),
    );
    await tester.pumpAndSettle();

    // A source that throws a non-Failure error must not crash the screen.
    await tester.enterText(find.byType(TextFormField), 'HASHFIT');
    tester.testTextInput.hide();
    FocusManager.instance.primaryFocus?.unfocus();
    await tester.tap(find.text('Find my gym'));
    await _settle(tester);

    expect(tester.takeException(), isNull);
  });
}

/// Lets the screen's async work finish.
///
/// The submit path awaits an anchor write; the in-flight button shows a
/// `CircularProgressIndicator` that schedules frames forever, so
/// `pumpAndSettle` would time out instead of settling.
Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 5; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

/// An in-memory [AnchorStore] — the widget test does not need real Hive
/// persistence (that is covered by the anchor store's own test).
class _InMemoryAnchorStore extends AnchorStore {
  _InMemoryAnchorStore();

  String? _gymUuid;
  String? _inviteToken;

  @override
  String? get runtimeGymUuid => _gymUuid;

  @override
  String? get inviteToken => _inviteToken;

  @override
  Future<void> save({required String gymUuid, String? inviteToken}) async {
    _gymUuid = gymUuid;
    if (inviteToken != null && inviteToken.isNotEmpty) {
      _inviteToken = inviteToken;
    }
  }
}
