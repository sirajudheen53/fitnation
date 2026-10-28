import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/auth/data/data_sources/api_client.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_notifier.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';
import 'package:fitnation_app/features/attendance/presentation/providers/check_in_providers.dart';
import 'package:fitnation_app/features/memberships/presentation/providers/membership_providers.dart';
import 'package:fitnation_app/features/payments/presentation/providers/payment_providers.dart';
import 'package:fitnation_app/features/plans/presentation/providers/plan_assignment_providers.dart';
import 'package:fitnation_app/router/app_router.dart';

import '../../../../helpers/attendance_fakes.dart';
import '../../../../helpers/fakes.dart';
import '../../../../helpers/membership_fakes.dart';
import '../../../../helpers/payment_fakes.dart';
import '../../../../helpers/plan_assignment_fakes.dart';

void main() {
  late FakeAuthRemoteDataSource remote;
  late FakeFirebaseAuthClient firebase;
  late AuthLocalDataSource local;
  late FakePlanAssignmentRemoteDataSource planRemote;
  late FakeAttendanceRemoteDataSource attendanceRemote;
  late FakeMembershipRemoteDataSource membershipRemote;
  late FakePaymentRemoteDataSource paymentRemote;
  late ProviderContainer container;

  setUp(() async {
    local = await setupTestAuthBox();
    ApiClient.reset();
    remote = FakeAuthRemoteDataSource();
    firebase = FakeFirebaseAuthClient();
    planRemote = FakePlanAssignmentRemoteDataSource();
    attendanceRemote = FakeAttendanceRemoteDataSource();
    membershipRemote = FakeMembershipRemoteDataSource();
    paymentRemote = FakePaymentRemoteDataSource();
    container = ProviderContainer(
      overrides: [
        authLocalDataSourceProvider.overrideWithValue(local),
        firebaseAuthClientProvider.overrideWithValue(firebase),
        authRemoteDataSourceProvider.overrideWithValue(remote),
        planAssignmentRepositoryProvider
            .overrideWithValue(FakePlanAssignmentRepository(planRemote)),
        attendanceRepositoryProvider
            .overrideWithValue(FakeAttendanceRepository(attendanceRemote)),
        membershipRepositoryProvider
            .overrideWithValue(FakeMembershipRepository(membershipRemote)),
        paymentRepositoryProvider
            .overrideWithValue(FakePaymentRepository(paymentRemote)),
      ],
    );
  });

  tearDown(() async {
    container.dispose();
    await teardownTestAuthBox();
  });

  void loginAs(UserModel user, List<String> permissions) {
    container.read(authProvider.notifier).state = AuthState(
      status: AuthStatus.authenticated,
      user: user,
      permissions: permissions,
    );
  }

  Future<void> pumpApp(WidgetTester tester) async {
    tester.view.physicalSize = const Size(412, 1000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: Consumer(
          builder: (context, ref, _) {
            // Mirrors FitNationApp: rebuild the router when auth state changes.
            return MaterialApp.router(routerConfig: ref.watch(routerProvider));
          },
        ),
      ),
    );
    await tester.pump();
  }

  const user = UserModel(
    id: 1,
    firstName: 'Arjun',
    lastName: 'Nair',
    role: 'customer',
    tenantName: 'Alpha Gym',
  );

  testWidgets('permission-gated tabs appear and Home greets the user', (
    tester,
  ) async {
    loginAs(user, const ['workouts.view_workout', 'diets.view_diet']);
    await pumpApp(tester);

    expect(find.text('Welcome back,'), findsOneWidget);
    expect(find.text('Arjun Nair'), findsOneWidget);
    expect(find.text('Alpha Gym'), findsOneWidget);
    // App bar title + navigation label for visible tabs.
    expect(find.text('Workouts'), findsWidgets);
    expect(find.text('Diet'), findsWidgets);
    expect(find.text('Attendance'), findsNothing); // no permission
    // The placeholder Quick Stats grid is gone (#95).
    expect(find.text('Quick Stats'), findsNothing);
  });

  testWidgets('home shows the member check-in state (#95)', (tester) async {
    attendanceRemote.checkInResult = [attendanceRecord()];
    loginAs(user, const []);
    await pumpApp(tester);
    await tester.pumpAndSettle();

    expect(find.text('You\'re checked in'), findsOneWidget);
    expect(find.text('Since 6:04 PM at Main'), findsOneWidget);
  });

  testWidgets('home dues card surfaces pending dues (#95)', (tester) async {
    paymentRemote.pendingResult = [pendingPayment()];
    membershipRemote.membershipResult = [membership()];
    loginAs(user, const []);
    await pumpApp(tester);
    await tester.pumpAndSettle();

    expect(find.text('₹1,500 due'), findsOneWidget);
    expect(find.text('Monthly'), findsOneWidget);
    expect(find.text('Active till 01 Nov 2026'), findsOneWidget);
  });

  testWidgets('tapping the workout plan row opens the workouts tab (#95)', (
    tester,
  ) async {
    planRemote.workoutResult = [workoutAssignment()];
    loginAs(user, const ['workouts.view_workout', 'diets.view_diet']);
    await pumpApp(tester);
    await tester.pumpAndSettle();

    await tester.tap(find.text('Workout plans'));
    await tester.pumpAndSettle();

    // Workouts tab is now showing (plan card + tab title).
    expect(find.text('Beginner Strength'), findsOneWidget);
  });

  testWidgets('workouts tab shows the assigned workout plan (#94)', (
    tester,
  ) async {
    planRemote.workoutResult = [workoutAssignment()];
    loginAs(user, const ['workouts.view_workout', 'diets.view_diet']);
    await pumpApp(tester);

    // The home summary row reuses this icon — target the nav bar only.
    await tester.tap(find.descendant(
      of: find.byType(NavigationBar),
      matching: find.byIcon(Icons.fitness_center_outlined),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Beginner Strength'), findsOneWidget);
    expect(find.text('Active'), findsOneWidget);
    // The home card primes the plan lists (#95), so the tab's initState
    // load is the second fetch.
    expect(planRemote.workoutCalls, 2);
  });

  testWidgets('diet tab shows the assigned meal plan (#94)', (tester) async {
    planRemote.dietResult = [dietAssignment()];
    loginAs(user, const ['workouts.view_workout', 'diets.view_diet']);
    await pumpApp(tester);

    await tester.tap(find.descendant(
      of: find.byType(NavigationBar),
      matching: find.byIcon(Icons.restaurant_outlined),
    ));
    await tester.pumpAndSettle();

    expect(find.text('High Protein Cut'), findsOneWidget);
    expect(planRemote.dietCalls, 2);
  });

  testWidgets('profile tab shows account details and permissions', (
    tester,
  ) async {
    loginAs(user, const ['workouts.view_workout']);
    await pumpApp(tester);

    await tester.tap(find.byIcon(Icons.person_outline));
    await tester.pumpAndSettle();

    expect(find.text('CUSTOMER'), findsOneWidget);
    expect(find.text('workouts.view_workout'), findsOneWidget);
    expect(find.text('Logout'), findsOneWidget);
  });

  testWidgets('logout clears the session and returns to the login route', (
    tester,
  ) async {
    loginAs(user, const []);
    await pumpApp(tester);

    await tester.tap(find.byIcon(Icons.logout_outlined));
    await tester.pumpAndSettle();

    expect(find.text('Are you sure you want to log out?'), findsOneWidget);

    await tester.tap(find.widgetWithText(TextButton, 'Logout').last);
    await tester.pumpAndSettle();

    expect(remote.logoutCalls, ['logout']);
    expect(firebase.signOutCalls, ['sign-out']);
    expect(container.read(authProvider).isAuthenticated, isFalse);
    expect(find.text('Welcome to FitNation'), findsOneWidget); // login screen
  });

  testWidgets('cancel keeps the user logged in', (tester) async {
    loginAs(user, const []);
    await pumpApp(tester);

    await tester.tap(find.byIcon(Icons.logout_outlined));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Cancel'));
    await tester.pumpAndSettle();

    expect(container.read(authProvider).isAuthenticated, isTrue);
    expect(remote.logoutCalls, isEmpty);
  });
}
