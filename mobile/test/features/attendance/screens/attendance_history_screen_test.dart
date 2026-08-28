import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/attendance/data/models/attendance_record.dart';
import 'package:fitnation_app/features/attendance/presentation/providers/attendance_provider.dart';
import 'package:fitnation_app/features/attendance/presentation/screens/attendance_history_screen.dart';

void main() {
  final today = DateTime.now();
  final records = [
    AttendanceRecord(
      id: 1,
      checkInTime: today,
      status: 'present',
    ),
    AttendanceRecord(
      id: 2,
      checkInTime: today.subtract(const Duration(days: 1)),
      status: 'present',
    ),
    AttendanceRecord(
      id: 3,
      checkInTime: today.subtract(const Duration(days: 2)),
      status: 'present',
    ),
  ];

  Widget buildWidget() {
    return ProviderScope(
      overrides: [
        attendanceHistoryProvider.overrideWith((ref) async => records),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const AttendanceHistoryScreen(),
      ),
    );
  }

  testWidgets('renders streak and history', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.text('Attendance'), findsOneWidget);
    expect(find.text('Current streak'), findsOneWidget);
    expect(find.text('3 days'), findsOneWidget);
    expect(find.text('History'), findsOneWidget);
    expect(find.text('Today'), findsOneWidget);
  });

  testWidgets('shows empty state when no records', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          attendanceHistoryProvider.overrideWith((ref) async => const []),
        ],
        child: MaterialApp(
          theme: AppTheme.light,
          home: const AttendanceHistoryScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('No attendance records yet'), findsOneWidget);
  });
}
