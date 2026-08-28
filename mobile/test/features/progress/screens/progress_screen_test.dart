import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/progress/data/models/body_measurement.dart';
import 'package:fitnation_app/features/progress/presentation/providers/progress_provider.dart';
import 'package:fitnation_app/features/progress/presentation/screens/progress_screen.dart';

void main() {
  final measurements = [
    BodyMeasurement(
      id: 1,
      measuredAt: DateTime(2026, 8, 24),
      weight: 75.5,
      bmi: 24.6,
      bodyFat: 18.0,
    ),
    BodyMeasurement(
      id: 2,
      measuredAt: DateTime(2026, 8, 17),
      weight: 76.0,
      bmi: 24.8,
      bodyFat: 18.5,
    ),
  ];

  final goals = [
    const FitnessGoal(
      id: 1,
      goalType: 'lose_weight',
      description: 'Lose 5kg',
      targetValue: 70.0,
      targetUnit: 'kg',
      currentValue: 75.5,
      progressPercentage: 45.0,
      status: 'active',
    ),
  ];

  Widget buildWidget() {
    return ProviderScope(
      overrides: [
        bodyMeasurementsProvider.overrideWith((ref) async => measurements),
        fitnessGoalsProvider.overrideWith((ref) async => goals),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const ProgressScreen(),
      ),
    );
  }

  testWidgets('renders latest stats, weight trend, and goals', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.text('Progress'), findsOneWidget);
    expect(find.text('Latest Measurements'), findsOneWidget);
    expect(find.text('Weight Trend'), findsOneWidget);
    expect(find.text('Fitness Goals'), findsOneWidget);
    expect(find.text('75.5 kg'), findsWidgets);
    expect(find.text('lose_weight'), findsOneWidget);
    expect(find.text('45% complete'), findsOneWidget);
  });

  testWidgets('shows empty state when no measurements', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          bodyMeasurementsProvider.overrideWith((ref) async => const []),
          fitnessGoalsProvider.overrideWith((ref) async => const []),
        ],
        child: MaterialApp(
          theme: AppTheme.light,
          home: const ProgressScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('No measurements yet'), findsOneWidget);
    expect(find.text('No goals set'), findsOneWidget);
  });
}
