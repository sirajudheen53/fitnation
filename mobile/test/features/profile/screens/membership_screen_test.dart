import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fitnation_app/features/profile/data/models/customer_profile.dart';
import 'package:fitnation_app/features/profile/presentation/providers/profile_provider.dart';
import 'package:fitnation_app/features/profile/presentation/screens/membership_screen.dart';

void main() {
  testWidgets('renders the membership card of an active membership', (tester) async {
    const membership = Membership(
      id: 3,
      planName: 'Gold',
      status: 'active',
      startDate: null,
      endDate: null,
      price: 12000,
      branchName: 'Adyar',
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          membershipsProvider.overrideWith((ref) async => [membership]),
        ],
        child: const MaterialApp(home: MembershipScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Membership'), findsOneWidget);
    expect(find.text('Gold'), findsOneWidget);
    expect(find.text('Active'), findsOneWidget);
    expect(find.text('Status'), findsOneWidget);
    expect(find.text('active'), findsOneWidget);
    expect(find.text('Start Date'), findsOneWidget);
    expect(find.text('—'), findsAtLeastNWidgets(2));
    expect(find.text('Price'), findsOneWidget);
    expect(find.text('₹12000'), findsOneWidget);
  });

  testWidgets('formats dates and marks an expired membership inactive', (tester) async {
    final membership = Membership(
      id: 4,
      planName: 'Silver',
      status: 'upcoming',
      startDate: DateTime(2026, 1, 2),
      endDate: DateTime(2026, 2, 1),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          membershipsProvider.overrideWith((ref) async => [membership]),
        ],
        child: const MaterialApp(home: MembershipScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Inactive'), findsOneWidget);
    expect(find.text('2/1/2026'), findsOneWidget);
    expect(find.text('1/2/2026'), findsOneWidget);
    expect(find.text('Price'), findsNothing);
  });

  testWidgets('shows a friendly empty state without any membership', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          membershipsProvider.overrideWith((ref) async => const <Membership>[]),
        ],
        child: const MaterialApp(home: MembershipScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('No membership found'), findsOneWidget);
    expect(find.text('Contact the gym to set up your membership.'), findsOneWidget);
  });
}