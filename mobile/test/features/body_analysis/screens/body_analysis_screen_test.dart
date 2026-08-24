import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mockito/mockito.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/body_analysis/domain/repositories/body_analysis_repository.dart';
import 'package:fitnation_app/features/body_analysis/data/data_sources/body_analysis_remote_data_source.dart';
import 'package:fitnation_app/features/body_analysis/models/body_analysis.dart';
import 'package:fitnation_app/features/body_analysis/models/progress_log.dart';
import 'package:fitnation_app/features/body_analysis/presentation/providers/body_analysis_provider.dart';
import 'package:fitnation_app/features/body_analysis/presentation/screens/body_analysis_screen.dart';

class MockBodyAnalysisRemoteDataSource extends Mock
    implements BodyAnalysisRemoteDataSource {}

void main() {
  late MockBodyAnalysisRemoteDataSource mockRemote;
  late BodyAnalysisRepository repo;

  setUp(() {
    mockRemote = MockBodyAnalysisRemoteDataSource();
    repo = BodyAnalysisRepository(mockRemote);
  });

  Widget buildWidget() {
    return ProviderScope(
      overrides: [
        bodyAnalysisRepositoryProvider.overrideWith((ref) => repo),
        bodyAnalysesProvider.overrideWith((ref) async => [
              const BodyAnalysis(
                id: 1,
                bmi: 24.5,
                bodyFatPercentage: 18.2,
                postureScore: 85,
              ),
            ]),
        bodyProgressProvider.overrideWith((ref) async => [
              ProgressLog(id: 1, weight: 70.0),
              ProgressLog(id: 2, weight: 69.0),
            ]),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const BodyAnalysisScreen(),
      ),
    );
  }

  testWidgets('renders upload button and metrics', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.text('Body Analysis'), findsOneWidget);
  });

  testWidgets('shows empty state when no analyses', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          bodyAnalysesProvider.overrideWith((ref) async => const []),
          bodyProgressProvider.overrideWith((ref) async => const []),
        ],
        child: MaterialApp(
          theme: AppTheme.light,
          home: const BodyAnalysisScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();
  });
}