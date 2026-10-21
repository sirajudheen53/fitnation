import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/access/presentation/widgets/grace_banner.dart';
import 'package:fitnation_app/features/auth/data/models/entitlement.dart';

void main() {
  Widget buildBanner(Entitlement entitlement) {
    return MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(
        body: GraceBanner(entitlement: entitlement),
      ),
    );
  }

  final expiredOn = DateTime(2026, 10, 14);
  final graceUntil = DateTime(2026, 10, 21);

  group('GraceBanner', () {
    testWidgets('states when the membership expired and when access ends',
        (tester) async {
      await tester.pumpWidget(buildBanner(Entitlement(
        status: AppEntitlementStatus.grace,
        readOnly: true,
        endDate: expiredOn,
        graceEndDate: graceUntil,
      )));

      expect(
        find.textContaining('Your membership expired on 14 Oct 2026'),
        findsOneWidget,
      );
      expect(
        find.textContaining('read-only until 21 Oct 2026'),
        findsOneWidget,
      );
    });

    testWidgets('points the member at renewing at the front desk',
        (tester) async {
      await tester.pumpWidget(buildBanner(Entitlement(
        status: AppEntitlementStatus.grace,
        readOnly: true,
        endDate: expiredOn,
        graceEndDate: graceUntil,
      )));

      expect(find.textContaining('renew at the front desk'), findsOneWidget);
    });

    testWidgets('degrades to a dash when no dates are known', (tester) async {
      await tester.pumpWidget(buildBanner(Entitlement(
        status: AppEntitlementStatus.grace,
        readOnly: true,
      )));

      expect(find.textContaining('expired on —'), findsOneWidget);
      expect(find.textContaining('read-only until —'), findsOneWidget);
    });

    testWidgets('formats the dates the same way as the gate page',
        (tester) async {
      // The banner and the gate page render the same dates for the same
      // member; a mismatch here would show two different "expired on" dates.
      expect(GraceBanner.formatDate(expiredOn), '14 Oct 2026');
      expect(GraceBanner.formatDate(graceUntil), '21 Oct 2026');
      expect(GraceBanner.formatDate(null), '—');
    });

    testWidgets('is a persistent notice, not a blocking screen',
        (tester) async {
      await tester.pumpWidget(buildBanner(Entitlement(
        status: AppEntitlementStatus.grace,
        readOnly: true,
        endDate: expiredOn,
        graceEndDate: graceUntil,
      )));

      // The banner is informational: it offers no dismiss action and no
      // button, so a grace member is never trapped behind it.
      expect(find.byType(ElevatedButton), findsNothing);
      expect(find.byType(TextButton), findsNothing);
      expect(find.byType(IconButton), findsNothing);
    });
  });

  group('showReadOnlySnack', () {
    testWidgets('explains that writes are blocked by the renewal',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        theme: AppTheme.light,
        home: Scaffold(
          body: Builder(
            builder: (context) => ElevatedButton(
              onPressed: () => showReadOnlySnack(context),
              child: const Text('Log workout'),
            ),
          ),
        ),
      ));

      await tester.tap(find.text('Log workout'));
      await tester.pump();

      expect(find.byType(SnackBar), findsOneWidget);
      expect(
        find.textContaining('Read-only mode'),
        findsOneWidget,
      );
      expect(
        find.textContaining('renew your membership'),
        findsOneWidget,
      );
    });

    testWidgets('points the member at the notice at the top of the screen',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        theme: AppTheme.light,
        home: Scaffold(
          body: Builder(
            builder: (context) => ElevatedButton(
              onPressed: () => showReadOnlySnack(context),
              child: const Text('Log workout'),
            ),
          ),
        ),
      ));

      await tester.tap(find.text('Log workout'));
      await tester.pump();

      expect(find.textContaining('notice at the top'), findsOneWidget);
    });
  });
}
