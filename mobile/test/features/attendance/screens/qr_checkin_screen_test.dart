import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/attendance/presentation/screens/qr_checkin_screen.dart';

void main() {
  group('QrCheckInScreen', () {
    testWidgets('renders title and QR input', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light,
            home: const QrCheckInScreen(),
          ),
        ),
      );

      expect(find.text('QR Check-in'), findsOneWidget);
      expect(find.text('QR Code'), findsOneWidget);
      expect(find.text('Check In'), findsOneWidget);
    });

    testWidgets('shows error when submitting empty QR code', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light,
            home: const QrCheckInScreen(),
          ),
        ),
      );

      await tester.tap(find.text('Check In'));
      await tester.pumpAndSettle();

      expect(find.text('Please enter or scan the QR code'), findsOneWidget);
    });
  });
}
