import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/attendance/presentation/providers/attendance_provider.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/domain/repositories/auth_repository.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';
import 'package:fitnation_app/features/dashboard/presentation/screens/dashboard_screen.dart';
import 'package:fitnation_app/features/diet/presentation/providers/diet_provider.dart';
import 'package:fitnation_app/features/progress/presentation/providers/progress_provider.dart';
import 'package:fitnation_app/features/workouts/presentation/providers/workout_provider.dart';

void main() {
  Widget buildWidget() {
    return ProviderScope(
      overrides: [
        authRepositoryProvider.overrideWithValue(_FakeAuthRepository()),
        activeWorkoutAssignmentProvider.overrideWith((ref) async => null),
        activeDietAssignmentProvider.overrideWith((ref) async => null),
        attendanceHistoryProvider.overrideWith((ref) async => const []),
        bodyMeasurementsProvider.overrideWith((ref) async => const []),
        fitnessGoalsProvider.overrideWith((ref) async => const []),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const DashboardScreen(),
      ),
    );
  }

  testWidgets('renders bottom navigation with 5 tabs', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.byType(NavigationBar), findsOneWidget);
    // 5 NavigationDestination widgets = 5 tabs
    expect(find.byType(NavigationDestination), findsNWidgets(5));
    // 'Workouts', 'Diet', 'Progress', 'Profile' are unique labels
    expect(find.text('Workouts'), findsOneWidget);
    expect(find.text('Diet'), findsOneWidget);
    expect(find.text('Progress'), findsOneWidget);
    expect(find.text('Profile'), findsOneWidget);
  });

  testWidgets('shows greeting on home tab', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.text('Welcome back,'), findsOneWidget);
    expect(find.text('Quick Actions'), findsOneWidget);
  });
}

/// Fake auth repository that returns a logged-in customer without Hive.
class _FakeAuthRepository extends AuthRepository {
  _FakeAuthRepository()
      : super(
          AuthRemoteDataSource(Dio()),
          _FakeLocalDataSource(),
        );

  @override
  ({UserModel? user, List<String> permissions, String? token}) restoreSession() {
    return (
      user: const UserModel(id: 3, role: 'customer', firstName: 'Raman'),
      permissions: const [],
      token: 'fake-token',
    );
  }
}

/// Fake local data source that returns a stored session without Hive.
class _FakeLocalDataSource extends AuthLocalDataSource {
  @override
  String? getToken() => 'fake-token';

  @override
  UserModel? getUser() =>
      const UserModel(id: 3, role: 'customer', firstName: 'Raman');

  @override
  List<String> getPermissions() => const [];

  @override
  bool get isAuthenticated => true;
}
