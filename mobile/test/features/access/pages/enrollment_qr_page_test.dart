import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:qr_flutter/qr_flutter.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/access/presentation/pages/enrollment_qr_page.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/domain/repositories/auth_repository.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_notifier.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';

void main() {
  Widget buildWidget({bool loggedIn = true}) {
    return ProviderScope(
      overrides: [
        authRepositoryProvider.overrideWithValue(_FakeAuthRepository()),
        if (loggedIn)
          authProvider.overrideWith(
            (ref) => _LoggedInAuthNotifier(_FakeAuthRepository()),
          ),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const EnrollmentQrPage(),
      ),
    );
  }

  testWidgets('renders QR code encoding customer id and tenant id', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.text('Enrollment QR'), findsWidgets);
    expect(find.byType(QrImageView), findsOneWidget);

    // QrImageView keeps its data private, so assert via the semantics label.
    expect(
      find.bySemanticsLabel('Enrollment QR: customer 42, gym 7'),
      findsOneWidget,
    );
    semantics.dispose();

    expect(find.text('Arun'), findsOneWidget);
    expect(find.text('FitNation HQ'), findsOneWidget);
    expect(find.text('Customer ID: 42'), findsOneWidget);
  });

  testWidgets('shows fallback card when the user is not loaded', (
    tester,
  ) async {
    await tester.pumpWidget(buildWidget(loggedIn: false));
    await tester.pumpAndSettle();

    expect(find.text('QR unavailable'), findsOneWidget);
    expect(find.byType(QrImageView), findsNothing);
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
      const UserModel(id: 42, role: 'customer', firstName: 'Arun');
}

/// Auth notifier pre-set to an authenticated customer with a tenant.
class _LoggedInAuthNotifier extends AuthNotifier {
  _LoggedInAuthNotifier(super.repository) {
    state = AuthState(
      status: AuthStatus.authenticated,
      user: const UserModel(
        id: 42,
        role: 'customer',
        firstName: 'Arun',
        tenantId: 7,
        tenantName: 'FitNation HQ',
      ),
    );
  }
}
