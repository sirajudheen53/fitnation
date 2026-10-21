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
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';
import 'package:fitnation_app/features/workouts/data/data_sources/workout_remote_data_source.dart';
import 'package:fitnation_app/features/workouts/data/models/exercise.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_exercise.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_log.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_plan.dart';
import 'package:fitnation_app/features/workouts/domain/repositories/workout_repository.dart';
import 'package:fitnation_app/features/workouts/presentation/providers/workout_provider.dart';
import 'package:fitnation_app/features/workouts/presentation/screens/workout_log_screen.dart';

const _day = WorkoutDay(
  id: 30,
  name: 'Day A',
  exercises: [
    WorkoutExercise(
      exercise: Exercise(id: 1, name: 'Squat'),
      targetSets: 2,
    ),
  ],
);
final _plan = WorkoutPlan(id: 20, name: 'Beginner Strength', days: [_day]);

void main() {
  Future<void> pumpScreen(
    WidgetTester tester, {
    required WorkoutLogNotifier notifier,
  }) async {
    final router = GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => Scaffold(
            body: Center(
              child: ElevatedButton(
                onPressed: () => context.push('/log'),
                child: const Text('Open log screen'),
              ),
            ),
          ),
        ),
        GoRoute(
          path: '/log',
          builder: (context, state) =>
              WorkoutLogScreen(plan: _plan, day: _day),
        ),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authRepositoryProvider.overrideWithValue(_FakeAuthRepository()),
          workoutLogProvider.overrideWith((ref) => notifier),
        ],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Open log screen'));
    await tester.pumpAndSettle();
  }

  testWidgets('renders the exercise section with two sets', (tester) async {
    await pumpScreen(tester, notifier: _StubLogNotifier());

    expect(find.text('Log Day A'), findsOneWidget);
    expect(find.text('Squat'), findsOneWidget);
    expect(find.text('Weight (kg)'), findsOneWidget);
    expect(find.text('Reps'), findsOneWidget);
    expect(find.text('Rest (s)'), findsOneWidget);
    expect(find.byType(Checkbox), findsNWidgets(2));
    expect(find.text('Submit Workout Log'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(8));
  });

  testWidgets('submitting with no completed sets is blocked', (tester) async {
    await pumpScreen(tester, notifier: _StubLogNotifier());

    await tester.enterText(find.byType(TextField).at(1), '10');
    await tester.tap(find.text('Submit Workout Log'));
    await tester.pumpAndSettle();

    expect(find.text('Mark at least one set as completed'), findsOneWidget);
  });

  testWidgets('a successful submit logs the sets and pops back', (tester) async {
    final notifier = _StubLogNotifier();
    await pumpScreen(tester, notifier: notifier);

    await tester.enterText(find.byType(TextField).at(0), '60');
    await tester.enterText(find.byType(TextField).at(1), '10');
    await tester.enterText(find.byType(TextField).at(2), '90');
    await tester.enterText(find.byType(TextField).at(4), '8');
    await tester.enterText(find.byType(TextField).at(6), '45');
    await tester.enterText(find.byType(TextField).at(7), 'felt strong');
    await tester.tap(find.byType(Checkbox).first);
    await tester.pump();
    await tester.tap(find.byType(Checkbox).at(1));
    await tester.pump();

    await tester.tap(find.text('Submit Workout Log'));
    await tester.pumpAndSettle();

    expect(find.text('Workout logged successfully!'), findsOneWidget);
    // Popped back to the placeholder route.
    expect(find.text('Open log screen'), findsOneWidget);

    final log = notifier.lastLog!;
    // The auth state is unpopulated outside app bootstrap, so the customer
    // id rides along as null and the backend stamps it from the token.
    expect(log.customerId, isNull);
    expect(log.planId, 20);
    expect(log.dayId, 30);
    expect(log.durationMinutes, 45);
    expect(log.notes, 'felt strong');
    expect(log.sets, hasLength(2));
    expect(log.sets.first.weight, 60.0);
    expect(log.sets.first.reps, 10);
    expect(log.sets.first.restSeconds, 90);
    expect(log.sets.last.weight, isNull);
    expect(log.sets.last.reps, 8);
  });

  testWidgets('a failed submit surfaces the error message', (tester) async {
    final notifier =
        _StubLogNotifier(success: false, errorMessage: 'Server on fire');
    await pumpScreen(tester, notifier: notifier);

    await tester.tap(find.byType(Checkbox).first);
    await tester.pump();
    await tester.tap(find.text('Submit Workout Log'));
    await tester.pumpAndSettle();

    expect(find.text('Server on fire'), findsOneWidget);
    // The screen stays up.
    expect(find.text('Submit Workout Log'), findsOneWidget);
  });
}

/// A notifier that skips the repository and records the submitted log.
class _StubLogNotifier extends WorkoutLogNotifier {
  _StubLogNotifier({this.success = true, this.errorMessage})
      : super(_NoopRepository());

  final bool success;
  final String? errorMessage;
  WorkoutLog? lastLog;

  @override
  Future<bool> logWorkout(WorkoutLog log) async {
    lastLog = log;
    state = WorkoutLogState(
      isSuccess: success,
      errorMessage: errorMessage,
    );
    return success;
  }
}

class _NoopRepository extends WorkoutRepository {
  _NoopRepository() : super(WorkoutRemoteDataSource(Dio()));
}

/// Fake auth repository returning a signed-in customer, no Hive.
class _FakeAuthRepository extends AuthRepository {
  _FakeAuthRepository()
      : super(AuthRemoteDataSource(Dio()), _FakeLocalDataSource());

  @override
  ({UserModel? user, List<String> permissions, String? token, Entitlement? entitlement})
      restoreSession() {
    return (
      user: const UserModel(id: 7, role: 'customer', firstName: 'Raman'),
      permissions: const [],
      token: 'fake-token',
      entitlement: const Entitlement(status: AppEntitlementStatus.active),
    );
  }
}

class _FakeLocalDataSource extends AuthLocalDataSource {
  @override
  String? getToken() => 'fake-token';

  @override
  UserModel? getUser() =>
      const UserModel(id: 7, role: 'customer', firstName: 'Raman');

  @override
  List<String> getPermissions() => const [];

  @override
  Entitlement? getEntitlement() =>
      const Entitlement(status: AppEntitlementStatus.active);
}