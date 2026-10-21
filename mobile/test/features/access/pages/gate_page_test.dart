import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/access/presentation/pages/gate_page.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/entitlement.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/domain/repositories/auth_repository.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_notifier.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';

void main() {
  Widget buildWidget(Entitlement entitlement) {
    final repository = _FakeAuthRepository();
    return ProviderScope(
      overrides: [
        authRepositoryProvider.overrideWithValue(repository),
        authProvider.overrideWith(
          (ref) => _GateAuthNotifier(repository, entitlement),
        ),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const GatePage(),
      ),
    );
  }

  group('gate — not entitled (`none`)', () {
    testWidgets('shows the friendly ask-your-gym screen', (tester) async {
      await tester.pumpWidget(
        buildWidget(
          const Entitlement(
            status: AppEntitlementStatus.none,
            gymName: 'Hash Fit',
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Welcome to Hash Fit!'), findsOneWidget);
      expect(find.textContaining('Ask the front desk'), findsOneWidget);
      // Not entitled: no member data, no crash, no dashboard.
      expect(find.text('Your membership has expired'), findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('offers a refresh and a log out', (tester) async {
      await tester.pumpWidget(
        buildWidget(const Entitlement(status: AppEntitlementStatus.none)),
      );
      await tester.pumpAndSettle();

      expect(find.text('I’ve renewed — refresh'), findsOneWidget);
      expect(find.text('Log out'), findsOneWidget);
    });
  });

  group('gate — expired (grace over)', () {
    testWidgets('shows the expired copy with the end date', (tester) async {
      await tester.pumpWidget(
        buildWidget(
          Entitlement(
            status: AppEntitlementStatus.expired,
            endDate: DateTime(2026, 10, 14),
            gymName: 'Hash Fit',
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Your membership has expired'), findsOneWidget);
      expect(find.textContaining('14 Oct 2026'), findsOneWidget);
      expect(find.textContaining('Renew at Hash Fit'), findsOneWidget);
    });

    testWidgets('falls back to a generic date when none is known', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildWidget(const Entitlement(status: AppEntitlementStatus.expired)),
      );
      await tester.pumpAndSettle();

      expect(
        find.textContaining('your last active day'),
        findsOneWidget,
      );
    });
  });

  group('gate — entitled', () {
    testWidgets('an entitled member is not shown the gate', (tester) async {
      await tester.pumpWidget(
        buildWidget(const Entitlement(status: AppEntitlementStatus.active)),
      );
      await tester.pumpAndSettle();

      // The gate page itself still renders, but the router redirect keeps
      // entitled members away — assert the state that drives that redirect.
      final auth = _GateAuthNotifier(
        _FakeAuthRepository(),
        const Entitlement(status: AppEntitlementStatus.active),
      );
      expect(auth.state.isGatedOut, isFalse);
    });

    testWidgets('a read-only grace member is not gated out', (tester) async {
      final notifier = _GateAuthNotifier(
        _FakeAuthRepository(),
        const Entitlement(
          status: AppEntitlementStatus.grace,
          readOnly: true,
        ),
      );

      expect(notifier.state.isGatedOut, isFalse);
      expect(notifier.state.isReadOnlyGrace, isTrue);
    });
  });

  group('revoked mid-session (FBOS-011 §2.4)', () {
    /// A notifier holding an active entitlement, as if the member were
    /// happily using the app.
    AuthNotifier activeNotifier() {
      final repository = _FakeAuthRepository();
      return _GateAuthNotifier(
        repository,
        const Entitlement(status: AppEntitlementStatus.active),
      );
    }

    test('an app_access_required 403 flips the member to the gate', () {
      final notifier = activeNotifier();

      // The member is happily in the app…
      expect(notifier.state.isGatedOut, isFalse);

      // …the server revokes the membership mid-session and the next call
      // comes back 403 app_access_required.
      notifier.applyAccessDeniedCode('app_access_required');

      expect(notifier.state.isGatedOut, isTrue);
      expect(
        notifier.state.entitlement?.status,
        AppEntitlementStatus.expired,
      );
    });

    test('an app_access_read_only 403 flips the member to grace', () {
      final notifier = activeNotifier();

      notifier.applyAccessDeniedCode('app_access_read_only');

      expect(notifier.state.isGatedOut, isFalse);
      expect(notifier.state.isReadOnlyGrace, isTrue);
    });

    test('an unrelated 403 code changes nothing', () {
      final notifier = activeNotifier();

      notifier.applyAccessDeniedCode('some_other_code');
      notifier.applyAccessDeniedCode(null);

      expect(notifier.state.isGatedOut, isFalse);
      expect(notifier.state.isReadOnlyGrace, isFalse);
    });

    test('a revocation keeps the gym name so the gate can show it', () {
      final repository = _FakeAuthRepository();
      final notifier = _GateAuthNotifier(
        repository,
        const Entitlement(
          status: AppEntitlementStatus.active,
          gymName: 'Hash Fit',
        ),
      );

      notifier.applyAccessDeniedCode('app_access_required');

      expect(notifier.state.entitlement?.gymName, 'Hash Fit');
    });
  });
}

/// Fake auth repository that avoids Hive/network access.
class _FakeAuthRepository extends AuthRepository {
  _FakeAuthRepository()
      : super(
          AuthRemoteDataSource(Dio()),
          _FakeLocalDataSource(),
        );
}

/// Fake local data source that avoids Hive.
class _FakeLocalDataSource extends AuthLocalDataSource {
  @override
  String? getToken() => 'fake-token';

  @override
  UserModel? getUser() =>
      const UserModel(id: 3, role: 'customer', firstName: 'Raman');
}

/// Auth notifier pre-set with an entitlement.
class _GateAuthNotifier extends AuthNotifier {
  _GateAuthNotifier(super.repository, Entitlement entitlement) {
    state = AuthState(
      status: AuthStatus.authenticated,
      user: const UserModel(
        id: 3,
        role: 'customer',
        firstName: 'Raman',
      ),
      entitlement: entitlement,
    );
  }
}
