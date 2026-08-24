import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/ai_coach/models/chat_message.dart';
import 'package:fitnation_app/features/ai_coach/presentation/widgets/message_bubble.dart';
import 'package:fitnation_app/features/ai_coach/presentation/screens/ai_chat_screen.dart';

void main() {
  Widget buildWidget({int? conversationId}) {
    return ProviderScope(
      child: MaterialApp(
        theme: AppTheme.light,
        home: AiChatScreen(conversationId: conversationId),
      ),
    );
  }

  testWidgets('renders AI Coach screen title', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.text('AI Coach'), findsOneWidget);
  });

  testWidgets('renders message bubble for user message', (tester) async {
    const message = ChatMessage(content: 'Hi', isUser: true);
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          theme: AppTheme.light,
          home: Scaffold(body: MessageBubble(message: message)),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Hi'), findsOneWidget);
  });

  testWidgets('renders message bubble for AI message', (tester) async {
    const message = ChatMessage(content: 'AI response', isUser: false);
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          theme: AppTheme.light,
          home: Scaffold(body: MessageBubble(message: message)),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('AI response'), findsOneWidget);
  });

  testWidgets('AI chat screen has text input and send button', (tester) async {
    await tester.pumpWidget(buildWidget());
    await tester.pumpAndSettle();

    expect(find.byType(TextField), findsOneWidget);
    expect(find.byIcon(Icons.send), findsOneWidget);
  });
}