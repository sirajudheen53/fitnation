import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/feedback/presentation/screens/feedback_form_screen.dart';

void main() {
  group('FeedbackFormScreen', () {
    testWidgets('renders title and form fields', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light,
            home: const FeedbackFormScreen(),
          ),
        ),
      );

      expect(find.text('Feedback'), findsOneWidget);
      expect(find.text('We value your feedback!'), findsOneWidget);
      expect(find.text('Your feedback'), findsOneWidget);
      expect(find.text('Submit Feedback'), findsOneWidget);
    });

    testWidgets('shows validation error for empty message', (tester) async {
      // Use a tall surface so the Submit button is on-screen.
      tester.view.physicalSize = const Size(800, 1600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light,
            home: const FeedbackFormScreen(),
          ),
        ),
      );

      await tester.tap(find.text('Submit Feedback'));
      await tester.pumpAndSettle();

      expect(find.text('Please enter your feedback'), findsOneWidget);
    });

    testWidgets('renders rating stars', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light,
            home: const FeedbackFormScreen(),
          ),
        ),
      );

      expect(find.byIcon(Icons.star_border), findsNWidgets(5));
    });

    testWidgets('renders category dropdown', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light,
            home: const FeedbackFormScreen(),
          ),
        ),
      );

      expect(find.text('Category'), findsOneWidget);
    });
  });
}
