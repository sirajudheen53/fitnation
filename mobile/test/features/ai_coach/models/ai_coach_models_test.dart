import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/ai_coach/models/chat_message.dart';
import 'package:fitnation_app/features/ai_coach/models/conversation.dart';
import 'package:fitnation_app/features/ai_coach/models/recommendation.dart';

void main() {
  group('ChatMessage', () {
    test('fromJson parses user message', () {
      final json = {
        'id': 1,
        'content': 'How do I improve my form?',
        'sender': 'user',
        'created_at': '2026-08-24T10:00:00Z',
      };

      final message = ChatMessage.fromJson(json);

      expect(message.id, 1);
      expect(message.content, 'How do I improve my form?');
      expect(message.isUser, isTrue);
      expect(message.createdAt, isNotNull);
    });

    test('fromJson parses AI message with recommendation', () {
      final json = {
        'id': 2,
        'content': 'Focus on your squat depth.',
        'sender': 'ai',
        'recommendation': 'Try lowering the weight',
      };

      final message = ChatMessage.fromJson(json);

      expect(message.isUser, isFalse);
      expect(message.recommendation, 'Try lowering the weight');
    });

    test('toJson reflects sender based on isUser', () {
      final message = ChatMessage(
        content: 'Hi',
        isUser: true,
      );

      expect(message.toJson()['sender'], 'user');
    });
  });

  group('Conversation', () {
    test('fromJson parses fields', () {
      final json = {
        'id': 5,
        'title': 'Form Check',
        'message_count': 3,
      };

      final conversation = Conversation.fromJson(json);

      expect(conversation.id, 5);
      expect(conversation.title, 'Form Check');
      expect(conversation.messageCount, 3);
    });

    test('defaults title to New Chat', () {
      final conversation = Conversation.fromJson({'id': 1});
      expect(conversation.title, 'New Chat');
    });
  });

  group('Recommendation', () {
    test('fromJson parses recommendation', () {
      final json = {
        'id': 1,
        'title': 'Rest more',
        'description': 'Take a rest day',
        'category': 'recovery',
        'priority': 1,
      };

      final recommendation = Recommendation.fromJson(json);

      expect(recommendation.title, 'Rest more');
      expect(recommendation.category, 'recovery');
      expect(recommendation.isApplied, isFalse);
    });
  });
}
