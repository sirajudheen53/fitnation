import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/auth/data/data_sources/api_client.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_notifier.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';
import 'package:fitnation_app/features/attendance/presentation/providers/check_in_providers.dart';
import 'package:fitnation_app/features/dashboard/presentation/screens/home_tab.dart';
import 'package:fitnation_app/features/memberships/presentation/providers/membership_providers.dart';
import 'package:fitnation_app/features/payments/presentation/providers/payment_providers.dart';
import 'package:fitnation_app/features/plans/presentation/providers/plan_assignment_providers.dart';

import '../../../../helpers/attendance_fakes.dart';
import '../../../../helpers/fakes.dart';
import '../../../../helpers/membership_fakes.dart';
import '../../../../helpers/payment_fakes.dart';
import '../../../../helpers/plan_assignment_fakes.dart';

void main() {
  late FakeAuthRemoteDataSource authRemote;
  late FakeFirebaseAuthClient firebase;
  late AuthLocalDataSource local;
  late FakeAttendanceRemoteDataSource attendanceRemote;
  late FakeMembershipRemoteDataSource membershipRemote;
  late FakePaymentRemoteDataSource paymentRemote;
  late FakePlanAssignmentRemoteDataSource planRemote;
  late ProviderContainer container;

  const user = UserModel(
    id: 1,
    firstName: 'Arjun',
    lastName: 'Nair',
    role: 'customer',
    tenantName: 'Alpha Gym',
  );

  setUp(() async {
    local = await setupTestAuthBox();
    ApiClient.reset();
    authRemote = FakeAuthRemoteDataSource();
    firebase = FakeFirebaseAuthClient();
    attendanceRemote = FakeAttendanceRemoteDataSource();
    membershipRemote = FakeMembershipRemoteDataSource();
    paymentRemote = FakePaymentRemoteDataSource();
    planRemote = FakePlanAssignmentRemoteDataSource();
    container = ProviderContainer(
      overrides: [
        authLocalDataSourceProvider.overrideWithValue(local),
        firebaseAuthClientProvider.overrideWithValue(firebase),
        authRemoteDataSourceProvider.overrideWithValue(authRemote),
        attendanceRepositoryProvider
            .overrideWithValue(FakeAttendanceRepository(attendanceRemote)),
        membershipRepositoryProvider
            .overrideWithValue(FakeMembershipRepository(membershipRemote)),
        paymentRepositoryProvider
            .overrideWithValue(FakePaymentRepository(paymentRemote)),
        planAssignmentRepositoryProvider
            .overrideWithValue(FakePlanAssignmentRepository(planRemote)),
      ],
    );
    container.read(authProvider.notifier).state = const AuthState(
      status: AuthStatus.authenticated,
      user: user,
    );
  });

  tearDown(() async {
    container.dispose();
    await teardownTestAuthBox();
  });

  Future<void> pumpHome(
    WidgetTester tester, {
    VoidCallback? onOpenWorkouts,
    VoidCallback? onOpenDiet,
  }) async {
    tester.view.physicalSize = const Size(412, 1000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          home: Scaffold(
            body: HomeTab(
              onOpenWorkouts: onOpenWorkouts,
              onOpenDiet: onOpenDiet,
            ),
          ),
        ),
      ),
    );
    await tester.pump();
  }

  testWidgets('greets the member and loads every section in parallel', (
    tester,
  ) async {
    attendanceRemote.checkInResult = [attendanceRecord()];
    membershipRemote.membershipResult = [membership()];
    paymentRemote.pendingResult = [pendingPayment()];
    planRemote.workoutResult = [workoutAssignment()];
    planRemote.dietResult = [dietAssignment()];

    await pumpHome(tester, onOpenWorkouts: () {}, onOpenDiet: () {});
    await tester.pumpAndSettle();

    expect(find.text('Welcome back,'), findsOneWidget);
    expect(find.text('Arjun Nair'), findsOneWidget);
    expect(find.text('Alpha Gym'), findsOneWidget);

    expect(find.text('You\'re checked in'), findsOneWidget);
    expect(find.text('Monthly'), findsOneWidget);
    expect(find.text('₹1,500 due'), findsOneWidget);
    expect(find.text('Beginner Strength'), findsOneWidget);
    expect(find.text('High Protein Cut'), findsOneWidget);

    // Every endpoint was hit exactly once.
    expect(attendanceRemote.checkInCalls, 1);
    expect(membershipRemote.membershipCalls, 1);
    expect(paymentRemote.pendingCalls, 1);
    expect(planRemote.workoutCalls, 1);
    expect(planRemote.dietCalls, 1);
  });

  testWidgets('shows honest empty states with no backend data', (tester) async {
    await pumpHome(tester, onOpenWorkouts: () {}, onOpenDiet: () {});
    await tester.pumpAndSettle();

    expect(find.text('No visits yet'), findsOneWidget);
    expect(find.text('No membership yet'), findsOneWidget);
    expect(find.text('None assigned'), findsNWidgets(2));
    expect(find.text('Quick Stats'), findsNothing);
  });

  testWidgets('plan rows are hidden when the member lacks the tabs', (
    tester,
  ) async {
    await pumpHome(tester);
    await tester.pumpAndSettle();

    expect(find.text('Your plans'), findsNothing);
  });

  testWidgets('tapping a plan row deep-links into its tab', (tester) async {
    var openedWorkouts = false;
    var openedDiet = false;

    await pumpHome(
      tester,
      onOpenWorkouts: () => openedWorkouts = true,
      onOpenDiet: () => openedDiet = true,
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Workout plans'));
    await tester.tap(find.text('Meal plans'));

    expect(openedWorkouts, isTrue);
    expect(openedDiet, isTrue);
  });
}
