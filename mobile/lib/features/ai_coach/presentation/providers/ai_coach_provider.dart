import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/data/data_sources/api_client.dart';
import '../../data/data_sources/ai_coach_remote_data_source.dart';
import '../../domain/repositories/ai_coach_repository.dart';
import '../../models/chat_message.dart';
import '../../models/conversation.dart';

/// Provides the AiCoachRemoteDataSource.
final aiCoachRemoteDataSourceProvider =
    Provider<AiCoachRemoteDataSource>((ref) {
  final dio = ApiClient.getInstance();
  return AiCoachRemoteDataSource(dio);
});

/// Provides the AiCoachRepository.
final aiCoachRepositoryProvider = Provider<AiCoachRepository>((ref) {
  final remote = ref.read(aiCoachRemoteDataSourceProvider);
  return AiCoachRepository(remote);
});

/// Fetches the list of conversations for the current customer.
final conversationsProvider = FutureProvider<List<Conversation>>((ref) async {
  final repo = ref.read(aiCoachRepositoryProvider);
  final result = await repo.getConversations();
  if (result.error != null) throw result.error!;
  return result.conversations ?? const [];
});

/// State of the chat screen.
class ChatState {
  final List<ChatMessage> messages;
  final bool isSending;
  final String? errorMessage;
  final int? conversationId;

  const ChatState({
    this.messages = const [],
    this.isSending = false,
    this.errorMessage,
    this.conversationId,
  });

  ChatState copyWith({
    List<ChatMessage>? messages,
    bool? isSending,
    String? errorMessage,
    int? conversationId,
  }) {
    return ChatState(
      messages: messages ?? this.messages,
      isSending: isSending ?? this.isSending,
      errorMessage: errorMessage,
      conversationId: conversationId ?? this.conversationId,
    );
  }
}

/// Notifier managing the chat message list and send flow.
class ChatNotifier extends StateNotifier<ChatState> {
  final AiCoachRepository _repository;

  ChatNotifier(this._repository) : super(const ChatState());

  /// Loads existing messages for a conversation.
  Future<void> loadMessages(int conversationId) async {
    final result = await _repository.getMessages(conversationId);
    if (result.error != null) {
      state = state.copyWith(
        errorMessage: result.error!.message,
        conversationId: conversationId,
      );
      return;
    }
    state = ChatState(
      messages: result.messages ?? const [],
      conversationId: conversationId,
    );
  }

  /// Sends a message and appends the AI reply.
  Future<bool> sendMessage(String text) async {
    if (text.trim().isEmpty || state.isSending) return false;

    final userMessage = ChatMessage(
      content: text.trim(),
      isUser: true,
      createdAt: DateTime.now(),
    );

    state = state.copyWith(
      messages: [...state.messages, userMessage],
      isSending: true,
      errorMessage: null,
    );

    final result = await _repository.chat(
      text.trim(),
      conversationId: state.conversationId,
    );

    if (result.error != null) {
      state = state.copyWith(
        isSending: false,
        errorMessage: result.error!.message,
      );
      return false;
    }

    final reply = result.message!;
    state = state.copyWith(
      messages: [...state.messages, reply],
      isSending: false,
      errorMessage: null,
      conversationId: reply.id != null
          ? state.conversationId
          : state.conversationId,
    );
    return true;
  }

  /// Clears the chat and starts fresh.
  void reset() {
    state = const ChatState();
  }
}

/// Provides the ChatNotifier.
final chatProvider =
    StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  final repo = ref.read(aiCoachRepositoryProvider);
  return ChatNotifier(repo);
});
