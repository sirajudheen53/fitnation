import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/auth/presentation/screens/phone_input_screen.dart';

void main() {
  group('PhoneInputScreen', () {
    testWidgets('renders brand logo and title', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light,
            home: const PhoneInputScreen(),
          ),
        ),
      );

      expect(find.text('Welcome to FitNation'), findsOneWidget);
      expect(find.text('Enter your phone number to get started'), findsOneWidget);
      expect(find.byIcon(Icons.fitness_center), findsOneWidget);
    });

    testWidgets('shows phone input field', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light,
            home: const PhoneInputScreen(),
          ),
        ),
      );

      expect(find.byType(TextFormField), findsOneWidget);
      expect(find.text('Phone Number'), findsOneWidget);
    });

    testWidgets('shows Send OTP button', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light,
            home: const PhoneInputScreen(),
          ),
        ),
      );

      expect(find.text('Send OTP'), findsOneWidget);
      expect(find.byType(ElevatedButton), findsOneWidget);
    });

    testWidgets('shows validation error for empty phone', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light,
            home: const PhoneInputScreen(),
          ),
        ),
      );

      // Tap the Send OTP button without entering phone
      await tester.tap(find.text('Send OTP'));
      await tester.pumpAndSettle();

      expect(find.text('Please enter your phone number'), findsOneWidget);
    });

    testWidgets('shows validation error for missing country code', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light,
            home: const PhoneInputScreen(),
          ),
        ),
      );

      await tester.enterText(find.byType(TextFormField), '9876543210');
      await tester.tap(find.text('Send OTP'));
      await tester.pumpAndSettle();

      expect(find.text('Include country code (e.g. +91)'), findsOneWidget);
    });
  });
}