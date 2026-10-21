import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/attendance/data/models/attendance_record.dart';
import 'package:fitnation_app/features/attendance/presentation/providers/attendance_provider.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/entitlement.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/domain/repositories/auth_repository.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';
import 'package:fitnation_app/features/dashboard/presentation/screens/dashboard_screen.dart';
import 'package:fitnation_app/features/diet/data/models/diet_plan.dart';
import 'package:fitnation_app/features/diet/data/models/meal.dart';
import 'package:fitnation_app/features/diet/presentation/providers/diet_provider.dart';
import 'package:fitnation_app/features/progress/data/models/body_measurement.dart';
import 'package:fitnation_app/features/progress/presentation/providers/progress_provider.dart';
import 'package:fitnation_app/features/workouts/data/models/exercise.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_exercise.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_plan.dart';
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

  testWidgets('tab navigation renders each tab body', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    await tester.tap(find.text('Workouts'));
    await tester.pumpAndSettle();
    expect(find.text('No active workout plan'), findsOneWidget);

    await tester.tap(find.text('Diet'));
    await tester.pumpAndSettle();
    expect(find.text('No active diet plan'), findsOneWidget);

    await tester.tap(find.text('Progress'));
    await tester.pumpAndSettle();
    expect(find.text('No measurements yet'), findsOneWidget);

    await tester.tap(find.text('Profile'));
    await tester.pumpAndSettle();
    // restoreSession only runs at app bootstrap, so the tab shows the
    // signed-out placeholders.
    expect(find.text('User'), findsOneWidget);
    expect(find.text('?'), findsOneWidget);
    expect(find.text('Enrollment QR'), findsOneWidget);
    expect(find.text('View Membership'), findsOneWidget);
    expect(find.text('Logout'), findsOneWidget);
  });

  testWidgets('today cards show the plan when assignments exist', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    final plan = WorkoutPlan(
      id: 20,
      name: 'Beginner Strength',
      days: [
        const WorkoutDay(
          name: 'Day A',
          exercises: [
            WorkoutExercise(exercise: Exercise(id: 1, name: 'Squat')),
            WorkoutExercise(exercise: Exercise(id: 2, name: 'Bench Press')),
          ],
        ),
      ],
    );
    const assignment = WorkoutAssignment(id: 1, customerId: 3, planId: 20);
    const dietAssignment = DietAssignment(id: 2, customerId: 3, planId: 30);
    final dietPlan = DietPlan(
      id: 30,
      name: 'Cut 8 weeks',
      days: [
        const DietDay(name: 'Day 1', meals: [
          Meal(name: 'Lunch', foodItems: [FoodItem(name: 'Rice', calories: 400)]),
        ]),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authRepositoryProvider.overrideWithValue(_FakeAuthRepository()),
          activeWorkoutAssignmentProvider.overrideWith((ref) async => assignment),
          workoutPlanProvider(20).overrideWith((ref) async => plan),
          activeDietAssignmentProvider.overrideWith((ref) async => dietAssignment),
          dietPlanProvider(30).overrideWith((ref) async => dietPlan),
          attendanceHistoryProvider.overrideWith((ref) async => const []),
          bodyMeasurementsProvider.overrideWith((ref) async => const []),
          fitnessGoalsProvider.overrideWith((ref) async => const []),
        ],
        child: MaterialApp(
          theme: AppTheme.light,
          home: const DashboardScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text("Today's Workout"), findsOneWidget);
    expect(find.text('Day A'), findsOneWidget);
    expect(find.text('2 exercises'), findsOneWidget);
    expect(find.text("Today's Diet"), findsOneWidget);
    expect(find.text('1 meals · 400 kcal'), findsOneWidget);

    // The Workouts tab embed reads the same providers with the plan present.
    await tester.tap(find.text('Workouts'));
    await tester.pumpAndSettle();
    expect(find.text('Day A'), findsOneWidget);
  });

  testWidgets('stats row shows the streak and latest weight/bmi', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final records = [
      AttendanceRecord(id: 4, checkInTime: now),
      AttendanceRecord(id: 3, checkInTime: today.subtract(const Duration(days: 1))),
      AttendanceRecord(id: 2, checkInTime: today.subtract(const Duration(days: 5))),
    ];
    const measurement = BodyMeasurement(id: 1, weight: 72.4, bmi: 23.6);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authRepositoryProvider.overrideWithValue(_FakeAuthRepository()),
          activeWorkoutAssignmentProvider.overrideWith((ref) async => null),
          activeDietAssignmentProvider.overrideWith((ref) async => null),
          attendanceHistoryProvider.overrideWith((ref) async => records),
          bodyMeasurementsProvider.overrideWith((ref) async => [measurement]),
          fitnessGoalsProvider.overrideWith((ref) async => const []),
        ],
        child: MaterialApp(
          theme: AppTheme.light,
          home: const DashboardScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('2'), findsOneWidget);
    expect(find.text('Day Streak'), findsOneWidget);
    expect(find.text('72.4 / 23.6'), findsOneWidget);
    expect(find.text('Weight / BMI'), findsOneWidget);
  });

  testWidgets('stats row shows a dash with no measurements', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.text('—'), findsOneWidget);
    expect(find.text('0'), findsOneWidget);
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
  ({UserModel? user, List<String> permissions, String? token, Entitlement? entitlement})
      restoreSession() {
    return (
      user: const UserModel(id: 3, role: 'customer', firstName: 'Raman'),
      permissions: const [],
      token: 'fake-token',
      entitlement: const Entitlement(status: AppEntitlementStatus.active),
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
