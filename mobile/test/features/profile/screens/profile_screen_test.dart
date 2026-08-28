import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/domain/repositories/auth_repository.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_notifier.dart';
import 'package:fitnation_app/features/profile/data/models/customer_profile.dart';
import 'package:fitnation_app/features/profile/presentation/providers/profile_provider.dart';
import 'package:fitnation_app/features/profile/presentation/screens/profile_screen.dart';

void main() {
  Widget buildWidget() {
    return ProviderScope(
      overrides: [
        authProvider.overrideWith((ref) => _FakeAuthNotifier()),
        customerProfileProvider.overrideWith(
          (ref) async => const CustomerProfile(
            id: 3,
            name: 'Raman Nair',
            email: 'raman@example.com',
            phone: '+919876543210',
            gender: 'male',
            emergencyContact: 'Priya Nair',
            emergencyPhone: '+919876543211',
            addressStreet: '12 MG Road',
            addressCity: 'Kochi',
          ),
        ),
        healthProfileProvider.overrideWith(
          (ref) async => const HealthProfile(
            id: 1,
            height: 175.0,
            weight: 75.5,
            bloodGroup: 'O+',
            medicalConditions: 'None',
          ),
        ),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const ProfileScreen(),
      ),
    );
  }

  testWidgets('renders profile name and details', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.text('Profile'), findsOneWidget);
    expect(find.text('Raman Nair'), findsOneWidget);
    expect(find.text('+919876543210'), findsOneWidget);
    expect(find.text('Health Information'), findsOneWidget);
    expect(find.text('175.0 cm'), findsOneWidget);
    expect(find.text('75.5 kg'), findsOneWidget);
  });

  testWidgets('shows empty state when no profile', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authProvider.overrideWith((ref) => _FakeAuthNotifier()),
          customerProfileProvider.overrideWith((ref) async => null),
          healthProfileProvider.overrideWith((ref) async => null),
        ],
        child: MaterialApp(
          theme: AppTheme.light,
          home: const ProfileScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Profile not found'), findsOneWidget);
    expect(find.text('No health profile on file.'), findsOneWidget);
  });
}

class _FakeAuthNotifier extends AuthNotifier {
  _FakeAuthNotifier()
      : super(
          AuthRepository(
            AuthRemoteDataSource(Dio()),
            AuthLocalDataSource(),
          ),
        ) {
    state = const AuthState(
      status: AuthStatus.authenticated,
      user: UserModel(
        id: 3,
        role: 'customer',
        firstName: 'Raman',
        lastName: 'Nair',
      ),
    );
  }
}
