import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';

void main() {
  testWidgets('light theme builds with brand colors', (tester) async {
    final theme = AppTheme.light;

    expect(theme, isA<ThemeData>());
    expect(theme.useMaterial3, isTrue);
    expect(theme.scaffoldBackgroundColor, AppTheme.background);
    expect(theme.appBarTheme.backgroundColor, AppTheme.surface);
    expect(theme.elevatedButtonTheme.style, isNotNull);
    expect(theme.inputDecorationTheme.filled, isTrue);
  });
}
