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
import 'package:fitnation_app/features/profile/presentation/screens/profile_edit_screen.dart';

void main() {
  Widget buildWidget() {
    return ProviderScope(
      overrides: [
        authProvider.overrideWith((ref) => _FakeAuthNotifier()),
        customerProfileProvider.overrideWith(
          (ref) async => const CustomerProfile(
            id: 3,
            name: 'Raman Nair',
            phone: '+919876543210',
          ),
        ),
        healthProfileProvider.overrideWith(
          (ref) async => const HealthProfile(
            id: 1,
            height: 175.0,
            weight: 75.5,
          ),
        ),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const ProfileEditScreen(),
      ),
    );
  }

  testWidgets('renders edit form with prefilled values', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.text('Edit Profile'), findsOneWidget);
    expect(find.text('Personal Information'), findsOneWidget);
    expect(find.text('Health Information'), findsOneWidget);

    // Prefilled values
    expect(find.text('Raman Nair'), findsOneWidget);
    expect(find.text('+919876543210'), findsOneWidget);
    expect(find.text('175.0'), findsOneWidget);
    expect(find.text('75.5'), findsOneWidget);

    // Scroll to the save button at the bottom of the form.
    await tester.drag(find.byType(ListView), const Offset(0, -600));
    await tester.pumpAndSettle();
    expect(find.text('Save Changes'), findsOneWidget);
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
      user: UserModel(id: 3, role: 'customer', firstName: 'Raman'),
    );
  }
}
