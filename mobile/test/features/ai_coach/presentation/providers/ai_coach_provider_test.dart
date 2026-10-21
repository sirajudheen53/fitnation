import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/ai_coach/domain/repositories/ai_coach_repository.dart';
import 'package:fitnation_app/features/ai_coach/models/chat_message.dart';
import 'package:fitnation_app/features/ai_coach/models/conversation.dart';
import 'package:fitnation_app/features/ai_coach/presentation/providers/ai_coach_provider.dart';

/// Repository whose chat call stalls until the test releases it.
class _StalledRepository implements AiCoachRepository {
  _StalledRepository(this._reply, void Function(int) count)
      : _count = count;

  final Completer<(ChatMessage?, Failure?)> _reply;
  final void Function(int) _count;

  @override
  Future<({ChatMessage? message, Failure? error})> chat(
    String message, {
    int? conversationId,
  }) async {
    _count(1);
    final (m, e) = await _reply.future;
    return (message: m, error: e);
  }

  @override
  Future<({List<Conversation>? conversations, Failure? error})>
      getConversations() async {
    return (conversations: null, error: const ServerFailure(message: 'unused'));
  }

  @override
  Future<({List<ChatMessage>? messages, Failure? error})> getMessages(
    int conversationId,
  ) async {
    return (messages: null, error: const ServerFailure(message: 'unused'));
  }
}

class _CannedRepository implements AiCoachRepository {
  _CannedRepository({
    this.conversationsResult,
    this.messagesResult,
    this.chatResult,
  });

  final (List<Conversation>?, Failure?)? conversationsResult;
  final (List<ChatMessage>?, Failure?)? messagesResult;
  final (ChatMessage?, Failure?)? chatResult;

  @override
  Future<({ChatMessage? message, Failure? error})> chat(
    String message, {
    int? conversationId,
  }) async {
    final canned = chatResult!;
    return (message: canned.$1, error: canned.$2);
  }

  @override
  Future<({List<Conversation>? conversations, Failure? error})>
      getConversations() async {
    final canned = conversationsResult!;
    return (conversations: canned.$1, error: canned.$2);
  }

  @override
  Future<({List<ChatMessage>? messages, Failure? error})> getMessages(
    int conversationId,
  ) async {
    final canned = messagesResult!;
    return (messages: canned.$1, error: canned.$2);
  }
}

const _reply = ChatMessage(content: 'You got this!', isUser: false);

void main() {
  ProviderContainer container(_CannedRepository repo) {
    final c = ProviderContainer(overrides: [
      aiCoachRepositoryProvider.overrideWithValue(repo),
    ]);
    addTearDown(c.dispose);
    return c;
  }

  group('conversationsProvider', () {
    test('surfaces conversations, or throws the failure', () async {
      final ok = container(_CannedRepository(
        conversationsResult: (const [Conversation(id: 4, title: 'Training')], null),
      ));
      expect((await ok.read(conversationsProvider.future)).single.title,
          'Training');

      final down = container(_CannedRepository(
        conversationsResult: (null, const ServerFailure(message: 'backend down')),
      ));
      await expectLater(
        down.read(conversationsProvider.future),
        throwsA(isA<ServerFailure>()),
      );
    });
  });

  group('ChatNotifier.loadMessages', () {
    test('loads the thread for a conversation', () async {
      final c = container(_CannedRepository(
        messagesResult: (const [ChatMessage(content: 'hello', isUser: true)], null),
      ));
      final notifier = c.read(chatProvider.notifier);

      await notifier.loadMessages(7);

      final state = c.read(chatProvider);
      expect(state.messages, hasLength(1));
      expect(state.conversationId, 7);
      expect(state.errorMessage, isNull);
    });

    test('keeps the conversation id and stores the error', () async {
      final c = container(_CannedRepository(
        messagesResult: (null, const ServerFailure(message: 'thread gone')),
      ));
      final notifier = c.read(chatProvider.notifier);

      await notifier.loadMessages(7);

      final state = c.read(chatProvider);
      expect(state.messages, isEmpty);
      expect(state.conversationId, 7);
      expect(state.errorMessage, 'thread gone');
    });
  });

  group('ChatNotifier.sendMessage', () {
    test('rejects empty text and double sends', () async {
      final reply = Completer<(ChatMessage?, Failure?)>();
      var chatCalls = 0;
      // Intercept at the provider level with a repo we can stall.
      final c2 = ProviderContainer(overrides: [
        aiCoachRepositoryProvider.overrideWithValue(_StalledRepository(reply, (n) => chatCalls += n)),
      ]);
      addTearDown(c2.dispose);
      final notifier = c2.read(chatProvider.notifier);

      // Empty text is rejected without touching the repository.
      expect(await notifier.sendMessage('   '), isFalse);
      expect(chatCalls, 0);

      // Start a send and try a second one while the first is in flight.
      final first = notifier.sendMessage('first');
      await c2.pump();
      expect(await notifier.sendMessage('second'), isFalse);
      expect(chatCalls, 1);

      reply.complete((_reply, null));
      expect(await first, isTrue);

      // The queued text never reaches the repository.
      final state = c2.read(chatProvider);
      expect(state.messages.last.content, 'You got this!');
      expect(state.messages, hasLength(2));
    });

    test('appends the user message and the AI reply', () async {
      final c = container(_CannedRepository(chatResult: (_reply, null)));
      final notifier = c.read(chatProvider.notifier);

      final ok = await notifier.sendMessage('how am I doing?');

      expect(ok, isTrue);
      final state = c.read(chatProvider);
      expect(state.messages, hasLength(2));
      expect(state.messages.first.isUser, isTrue);
      expect(state.messages.first.content, 'how am I doing?');
      expect(state.messages.last.isUser, isFalse);
      expect(state.messages.last.content, 'You got this!');
      expect(state.isSending, isFalse);
      expect(state.errorMessage, isNull);
    });

    test('a failed send flags the error and returns false', () async {
      final c = container(_CannedRepository(
        chatResult: (null, const ServerFailure(message: 'AI coach down')),
      ));
      final notifier = c.read(chatProvider.notifier);

      final ok = await notifier.sendMessage('hello?');

      expect(ok, isFalse);
      final state = c.read(chatProvider);
      expect(state.messages, hasLength(1));
      expect(state.messages.first.isUser, isTrue);
      expect(state.isSending, isFalse);
      expect(state.errorMessage, 'AI coach down');
    });

    test('reset starts a fresh thread', () async {
      final c = container(_CannedRepository(chatResult: (_reply, null)));
      final notifier = c.read(chatProvider.notifier);
      await notifier.sendMessage('hello');

      notifier.reset();

      expect(c.read(chatProvider), const ChatState());
    });
  });
}