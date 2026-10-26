import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/auth/presentation/widgets/gym_selection_panel.dart';

void main() {
  Future<void> pumpPanel(
    WidgetTester tester, {
    required List<GymOption> gyms,
    bool isBusy = false,
    ValueChanged<String>? onConfirm,
  }) {
    return tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GymSelectionPanel(
            gyms: gyms,
            isBusy: isBusy,
            onConfirm: onConfirm ?? (_) {},
          ),
        ),
      ),
    );
  }

  testWidgets('shows the specify-your-gym headline', (tester) async {
    await pumpPanel(
      tester,
      gyms: const [GymOption(id: '1', name: 'Alpha Gym')],
    );

    expect(find.text('Specify your gym to continue'), findsOneWidget);
  });

  testWidgets('dropdown flow: continue disabled until a gym is picked', (
    tester,
  ) async {
    String? confirmed;
    await pumpPanel(
      tester,
      gyms: const [
        GymOption(id: '1', name: 'Alpha Gym'),
        GymOption(id: '2', name: 'Beta Gym'),
      ],
      onConfirm: (gymId) => confirmed = gymId,
    );

    // Continue is disabled before a selection.
    final continueFinder = find.widgetWithText(ElevatedButton, 'Continue');
    expect(tester.widget<ElevatedButton>(continueFinder).onPressed, isNull);

    await tester.tap(find.text('Select your gym'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Alpha Gym').last);
    await tester.pumpAndSettle();

    expect(tester.widget<ElevatedButton>(continueFinder).onPressed, isNotNull);
    await tester.tap(continueFinder);
    await tester.pump();

    expect(confirmed, '1');
  });

  testWidgets('manual entry flow when no gyms are offered', (tester) async {
    String? confirmed;
    await pumpPanel(
      tester,
      gyms: const [],
      onConfirm: (gymId) => confirmed = gymId,
    );

    expect(find.byType(DropdownButtonFormField<String>), findsNothing);
    expect(find.byType(TextField), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'FitNation Koramangala');
    await tester.pump();

    await tester.tap(find.widgetWithText(ElevatedButton, 'Continue'));
    await tester.pump();

    expect(confirmed, 'FitNation Koramangala');
  });

  testWidgets('busy state disables submit and shows a spinner', (tester) async {
    await pumpPanel(
      tester,
      gyms: const [GymOption(id: '1', name: 'Alpha Gym')],
      isBusy: true,
    );

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(
      tester.widget<ElevatedButton>(find.byType(ElevatedButton)).onPressed,
      isNull,
    );
  });
}
