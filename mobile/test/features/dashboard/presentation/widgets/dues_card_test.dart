import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/memberships/presentation/providers/membership_providers.dart';
import 'package:fitnation_app/features/dashboard/presentation/widgets/dues_card.dart';
import 'package:fitnation_app/features/payments/presentation/providers/payment_providers.dart';

import '../../../../helpers/membership_fakes.dart';
import '../../../../helpers/payment_fakes.dart';

void main() {
  Future<void> pumpCard(
    WidgetTester tester, {
    required MembershipState membership,
    required PendingPaymentsState dues,
    required void Function() onRetry,
  }) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: DuesCard(
            membership: membership,
            dues: dues,
            onRetry: () async => onRetry(),
          ),
        ),
      ),
    );
  }

  testWidgets('active membership with no dues shows both lines', (tester) async {
    await pumpCard(
      tester,
      membership: MembershipState(
        status: MembershipStatus.loaded,
        membership: membership(),
      ),
      dues: const PendingPaymentsState(status: PendingPaymentsStatus.loaded),
      onRetry: () {},
    );

    expect(find.text('Monthly'), findsOneWidget);
    expect(find.text('Active till 01 Nov 2026'), findsOneWidget);
    expect(find.text('No pending dues'), findsOneWidget);
    expect(find.text('₹1,500 due'), findsNothing);
  });

  testWidgets('pending dues render the total and the plan breakdown', (
    tester,
  ) async {
    await pumpCard(
      tester,
      membership: MembershipState(
        status: MembershipStatus.loaded,
        membership: membership(),
      ),
      dues: PendingPaymentsState(
        status: PendingPaymentsStatus.loaded,
        payments: [pendingPayment()],
      ),
      onRetry: () {},
    );

    expect(find.text('₹1,500 due'), findsOneWidget);
    expect(find.text('Monthly · pending'), findsOneWidget);
    expect(find.text('No pending dues'), findsNothing);
  });

  testWidgets('several pending dues are counted in the breakdown', (
    tester,
  ) async {
    await pumpCard(
      tester,
      membership: const MembershipState(status: MembershipStatus.loaded),
      dues: PendingPaymentsState(
        status: PendingPaymentsStatus.loaded,
        payments: [pendingPayment(), pendingPayment(id: 11, amount: '250.50')],
      ),
      onRetry: () {},
    );

    expect(find.text('₹1,750.50 due'), findsOneWidget);
    expect(find.text('Monthly · 2 pending payments'), findsOneWidget);
  });

  testWidgets('an expired membership says so with the end date', (tester) async {
    await pumpCard(
      tester,
      membership: MembershipState(
        status: MembershipStatus.loaded,
        membership: membership(status: 'expired'),
      ),
      dues: PendingPaymentsState(
        status: PendingPaymentsStatus.loaded,
        payments: [pendingPayment()],
      ),
      onRetry: () {},
    );

    expect(find.text('Expired on 01 Nov 2026'), findsOneWidget);
  });

  testWidgets('no membership at all shows the setup hint', (tester) async {
    await pumpCard(
      tester,
      membership:
          const MembershipState(status: MembershipStatus.loaded),
      dues: const PendingPaymentsState(status: PendingPaymentsStatus.loaded),
      onRetry: () {},
    );

    expect(find.text('No membership yet'), findsOneWidget);
  });

  testWidgets('first load shows a compact loading row', (tester) async {
    await pumpCard(
      tester,
      membership: const MembershipState(status: MembershipStatus.loading),
      dues:
          const PendingPaymentsState(status: PendingPaymentsStatus.loading),
      onRetry: () {},
    );

    expect(find.text('Loading your membership…'), findsOneWidget);
  });

  testWidgets('double error shows the message and retry re-triggers', (
    tester,
  ) async {
    var retries = 0;
    await pumpCard(
      tester,
      membership: const MembershipState(
        status: MembershipStatus.error,
        errorMessage: 'Couldn\'t load your membership.',
      ),
      dues: const PendingPaymentsState(
        status: PendingPaymentsStatus.error,
        errorMessage: 'Couldn\'t load your dues.',
      ),
      onRetry: () => retries++,
    );

    expect(find.text('Couldn\'t load your membership.'), findsOneWidget);

    await tester.tap(find.text('Retry'));
    expect(retries, 1);
  });

  testWidgets('a dues error still shows the membership line', (tester) async {
    await pumpCard(
      tester,
      membership: MembershipState(
        status: MembershipStatus.loaded,
        membership: membership(),
      ),
      dues: const PendingPaymentsState(
        status: PendingPaymentsStatus.error,
        errorMessage: 'Network error. Check your connection.',
      ),
      onRetry: () {},
    );

    expect(find.text('Monthly'), findsOneWidget);
    expect(find.text('Couldn\'t load your dues.'), findsNothing);
    expect(find.text('No pending dues'), findsNothing);
  });
}
