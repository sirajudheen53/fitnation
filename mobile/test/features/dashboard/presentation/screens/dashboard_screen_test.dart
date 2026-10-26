import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/auth/data/data_sources/api_client.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_notifier.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';
import 'package:fitnation_app/router/app_router.dart';

import '../../../../helpers/fakes.dart';

void main() {
  late FakeAuthRemoteDataSource remote;
  late FakeFirebaseAuthClient firebase;
  late AuthLocalDataSource local;
  late ProviderContainer container;

  setUp(() async {
    local = await setupTestAuthBox();
    ApiClient.reset();
    remote = FakeAuthRemoteDataSource();
    firebase = FakeFirebaseAuthClient();
    container = ProviderContainer(
      overrides: [
        authLocalDataSourceProvider.overrideWithValue(local),
        firebaseAuthClientProvider.overrideWithValue(firebase),
        authRemoteDataSourceProvider.overrideWithValue(remote),
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
