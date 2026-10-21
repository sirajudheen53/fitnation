import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/domain/repositories/auth_repository.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_notifier.dart';
import 'package:fitnation_app/features/profile/data/data_sources/profile_remote_data_source.dart';
import 'package:fitnation_app/features/profile/data/models/customer_profile.dart';
import 'package:fitnation_app/features/profile/domain/repositories/profile_repository.dart';
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

  testWidgets('saving updates the profile and the health profile', (tester) async {
    final notifier = _RecordingEditNotifier();
    await tester.pumpWidget(pumpedRouterWidget(notifier: notifier));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Open edit screen'));
    await tester.pumpAndSettle();

    // Scroll to the bottom and save.
    await tester.drag(find.byType(ListView), const Offset(0, -600));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save Changes'));
    await tester.pumpAndSettle();

    expect(find.text('Profile updated'), findsOneWidget);
    expect(find.text('Open edit screen'), findsOneWidget);

    expect(notifier.profileCalls.single, {
      'name': 'Raman Nair',
      'phone': '+919876543210',
      'emergency_contact_name': '',
      'emergency_contact_phone': '',
      'address_street': '',
    });
    expect(notifier.healthCalls.single['height_cm'], 175.0);
    expect(notifier.healthCalls.single['weight_kg'], 75.5);
  });

  testWidgets('a failed profile save surfaces the error and stays', (tester) async {
    final notifier = _RecordingEditNotifier(profileError: 'Phone is taken');
    await tester.pumpWidget(pumpedRouterWidget(notifier: notifier));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Open edit screen'));
    await tester.pumpAndSettle();

    await tester.drag(find.byType(ListView), const Offset(0, -600));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save Changes'));
    await tester.pumpAndSettle();

    expect(find.text('Phone is taken'), findsOneWidget);
    expect(find.text('Save Changes'), findsOneWidget);
  });

  testWidgets('a failed health save surfaces its own error', (tester) async {
    final notifier = _RecordingEditNotifier(healthError: 'Weight out of range');
    await tester.pumpWidget(pumpedRouterWidget(notifier: notifier));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Open edit screen'));
    await tester.pumpAndSettle();

    await tester.drag(find.byType(ListView), const Offset(0, -600));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save Changes'));
    await tester.pumpAndSettle();

    expect(find.text('Weight out of range'), findsOneWidget);
    expect(find.text('Save Changes'), findsOneWidget);
  });
}

Widget pumpedRouterWidget({required ProfileEditNotifier notifier}) {
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(
        path: '/',
        builder: (context, state) => Scaffold(
          body: Center(
            child: ElevatedButton(
              onPressed: () => context.push('/edit'),
              child: const Text('Open edit screen'),
            ),
          ),
        ),
      ),
      GoRoute(
        path: '/edit',
        builder: (context, state) => const ProfileEditScreen(),
      ),
    ],
  );

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
      profileEditProvider.overrideWith((ref) => notifier),
    ],
    child: MaterialApp.router(routerConfig: router),
  );
}

/// An edit notifier that records what the screen asked it to save.
class _RecordingEditNotifier extends ProfileEditNotifier {
  _RecordingEditNotifier({this.profileError, this.healthError})
      : super(_NoopRepository());

  final String? profileError;
  final String? healthError;
  final List<Map<String, dynamic>> profileCalls = [];
  final List<Map<String, dynamic>> healthCalls = [];

  @override
  Future<bool> updateProfile(int customerId, Map<String, dynamic> data) async {
    profileCalls.add(data);
    state = ProfileEditState(isSaving: false, errorMessage: profileError);
    return profileError == null;
  }

  @override
  Future<bool> updateHealthProfile(
    int customerId,
    Map<String, dynamic> data,
  ) async {
    healthCalls.add(data);
    state = ProfileEditState(isSaving: false, errorMessage: healthError);
    return healthError == null;
  }
}

class _NoopRepository extends ProfileRepository {
  _NoopRepository() : super(ProfileRemoteDataSource(Dio()));
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
