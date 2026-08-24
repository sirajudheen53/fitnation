import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mockito/mockito.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/body_analysis/domain/repositories/body_analysis_repository.dart';
import 'package:fitnation_app/features/body_analysis/presentation/providers/body_analysis_provider.dart';
import 'package:fitnation_app/features/body_analysis/presentation/screens/upload_photo_screen.dart';

class MockBodyAnalysisRepository extends Mock
    implements BodyAnalysisRepository {}

void main() {
  late MockBodyAnalysisRepository mockRepo;

  setUp(() {
    mockRepo = MockBodyAnalysisRepository();
  });

  Widget buildWidget() {
    return ProviderScope(
      overrides: [
        bodyAnalysisRepositoryProvider.overrideWith((ref) => mockRepo),
        uploadProvider.overrideWith((ref) => UploadNotifier(mockRepo)),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const UploadPhotoScreen(),
      ),
    );
  }

  testWidgets('renders photo type selectors', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.text('Upload Photo'), findsOneWidget);
    expect(find.text('Front'), findsOneWidget);
    expect(find.text('Side'), findsOneWidget);
    expect(find.text('Back'), findsOneWidget);
    expect(find.text('Submit'), findsOneWidget);
  });

  testWidgets('shows snackbar when submitting without photo', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    await tester.tap(find.text('Submit'));
    await tester.pumpAndSettle();

    expect(find.text('Please select a photo first.'), findsOneWidget);
  });

  testWidgets('selects a photo type', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    await tester.tap(find.text('Back'));
    await tester.pumpAndSettle();

    // Selecting "Back" should mark it as selected (primary-colored border).
    // No crash and still renders.
    expect(find.text('Back'), findsOneWidget);
  });
}
