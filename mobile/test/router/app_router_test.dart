import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/entitlement.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/domain/repositories/auth_repository.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_notifier.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';
import 'package:fitnation_app/router/app_router.dart';

void main() {
  /// Builds the app router with a known auth state and returns the router
  /// plus the notifier so the test can flip the entitlement.
  ({GoRouter router, AuthNotifier notifier, ProviderContainer container})
      buildRouter({
    bool authenticated = true,
    Entitlement? entitlement,
  }) {
    final repository = _FakeAuthRepository();
    final notifier = _RouterAuthNotifier(
      repository,
      authenticated: authenticated,
      entitlement: entitlement,
    );

    final container = ProviderContainer(
      overrides: [
        authRepositoryProvider.overrideWithValue(repository),
        authProvider.overrideWith((ref) => notifier),
      ],
    );

    final router = container.read(routerProvider);
    return (router: router, notifier: notifier, container: container);
  }

  group('redirect', () {
    testWidgets('an unauthenticated member is sent to the phone input', (
      tester,
    ) async {
      final built = buildRouter(authenticated: false);
      final router = built.router;
      await _pump(tester, router, built.container);

      router.go('/dashboard');
      await tester.pumpAndSettle();

      expect(router.routeInformationProvider.value.uri.path, '/');
    });

    testWidgets('an authenticated member lands on the dashboard', (
      tester,
    ) async {
      final built = buildRouter(
        entitlement: const Entitlement(status: AppEntitlementStatus.active),
      );
      final router = built.router;
      await _pump(tester, router, built.container);

      router.go('/');
      await tester.pumpAndSettle();

      expect(
        router.routeInformationProvider.value.uri.path,
        '/dashboard',
      );
    });

    testWidgets('a gated-out member is sent to the gate', (tester) async {
      final built = buildRouter(
        entitlement: const Entitlement(status: AppEntitlementStatus.expired),
      );
      final router = built.router;
      await _pump(tester, router, built.container);

      router.go('/dashboard');
      await tester.pumpAndSettle();

      expect(router.routeInformationProvider.value.uri.path, '/gate');
    });

    testWidgets('a member with no entitlement is sent to the gate', (
      tester,
    ) async {
      final built = buildRouter(
        entitlement: const Entitlement(status: AppEntitlementStatus.none),
      );
      final router = built.router;
      await _pump(tester, router, built.container);

      router.go('/workouts');
      await tester.pumpAndSettle();

      expect(router.routeInformationProvider.value.uri.path, '/gate');
    });

    testWidgets('a read-only grace member keeps the app', (tester) async {
      final built = buildRouter(
        entitlement: const Entitlement(
          status: AppEntitlementStatus.grace,
          readOnly: true,
        ),
      );
      final router = built.router;
      await _pump(tester, router, built.container);

      router.go('/dashboard');
      await tester.pumpAndSettle();

      expect(
        router.routeInformationProvider.value.uri.path,
        '/dashboard',
      );
    });

    testWidgets('the gym-code screen is reachable while signed out', (
      tester,
    ) async {
      final built = buildRouter(authenticated: false);
      final router = built.router;
      await _pump(tester, router, built.container);

      router.go('/gym-code');
      await tester.pumpAndSettle();

      expect(
        router.routeInformationProvider.value.uri.path,
        '/gym-code',
      );
    });

    testWidgets('a signed-in member is moved off the gym-code screen', (
      tester,
    ) async {
      final built = buildRouter(
        entitlement: const Entitlement(status: AppEntitlementStatus.active),
      );
      final router = built.router;
      await _pump(tester, router, built.container);

      router.go('/gym-code');
      await tester.pumpAndSettle();

      expect(
        router.routeInformationProvider.value.uri.path,
        '/dashboard',
      );
    });
  });

  group('mid-session revocation (FBOS-011 §9.4)', () {
    testWidgets('a revoked member is moved to the gate on the next frame', (
      tester,
    ) async {
      final built = buildRouter(
        entitlement: const Entitlement(status: AppEntitlementStatus.active),
      );
      final router = built.router;
      await _pump(tester, router, built.container);

      router.go('/dashboard');
      await tester.pumpAndSettle();
      expect(
        router.routeInformationProvider.value.uri.path,
        '/dashboard',
      );

      // The server revokes the membership; the Dio interceptor reports it.
      built.notifier.applyAccessDeniedCode('app_access_required');
      await tester.pumpAndSettle();

      // The router re-runs the redirect off the auth-state change.
      expect(
        router.routeInformationProvider.value.uri.path,
        '/gate',
      );
      expect(built.notifier.state.isGatedOut, isTrue);
    });
  });
}

/// Mounts the router so GoRouter resolves the route (and its redirect).
///
/// The screens read the auth state from the same [ProviderContainer] the
/// router listens to, so the scope has to wrap the router too.
Future<void> _pump(
  WidgetTester tester,
  GoRouter router,
  ProviderContainer container,
) async {
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
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

/// Auth notifier with a settable auth state.
class _RouterAuthNotifier extends AuthNotifier {
  _RouterAuthNotifier(
    super.repository, {
    required bool authenticated,
    Entitlement? entitlement,
  }) {
    state = AuthState(
      status: authenticated
          ? AuthStatus.authenticated
          : AuthStatus.unauthenticated,
      user: authenticated
          ? const UserModel(id: 3, role: 'customer', firstName: 'Raman')
          : null,
      entitlement: entitlement,
    );
  }
}
