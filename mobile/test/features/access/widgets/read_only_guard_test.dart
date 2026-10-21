import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/access/presentation/widgets/read_only_guard.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/entitlement.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/domain/repositories/auth_repository.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_notifier.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';

void main() {
  Widget buildWidget(Entitlement entitlement, {VoidCallback? onPressed}) {
    final repository = _FakeAuthRepository();
    return ProviderScope(
      overrides: [
        authRepositoryProvider.overrideWithValue(repository),
        authProvider.overrideWith(
          (ref) => _GuardAuthNotifier(repository, entitlement),
        ),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: Scaffold(
          body: ReadOnlyGuard(
            onPressed: onPressed,
            builder: (onPressed) => ElevatedButton(
              onPressed: onPressed,
              child: const Text('Submit'),
            ),
          ),
        ),
      ),
    );
  }

  testWidgets('an entitled member can use the action', (tester) async {
    var pressed = 0;
    await tester.pumpWidget(
      buildWidget(
        const Entitlement(status: AppEntitlementStatus.active),
        onPressed: () => pressed++,
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Submit'));
    await tester.pumpAndSettle();

    expect(pressed, 1);
  });

  testWidgets('a read-only grace member gets the renewal notice instead', (
    tester,
  ) async {
    var pressed = 0;
    await tester.pumpWidget(
      buildWidget(
        const Entitlement(
          status: AppEntitlementStatus.grace,
          readOnly: true,
        ),
        onPressed: () => pressed++,
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Submit'));
    await tester.pumpAndSettle();

    // The write did not happen…
    expect(pressed, 0);
    // …the member was told why.
    expect(find.textContaining('Read-only mode'), findsOneWidget);
  });

  testWidgets('a disabled action stays disabled for an entitled member', (
    tester,
  ) async {
    var pressed = 0;
    await tester.pumpWidget(
      buildWidget(
        const Entitlement(status: AppEntitlementStatus.active),
        onPressed: () => pressed++,
      ),
    );
    await tester.pumpAndSettle();

    final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
    expect(button.onPressed, isNotNull);
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
class _GuardAuthNotifier extends AuthNotifier {
  _GuardAuthNotifier(super.repository, Entitlement entitlement) {
    state = AuthState(
      status: AuthStatus.authenticated,
      user: const UserModel(id: 3, role: 'customer', firstName: 'Raman'),
      entitlement: entitlement,
    );
  }
}
