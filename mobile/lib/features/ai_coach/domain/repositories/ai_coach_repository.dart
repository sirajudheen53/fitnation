import '../../../../core/errors/failures.dart';
import '../../data/data_sources/ai_coach_remote_data_source.dart';
import '../../models/chat_message.dart';
import '../../models/conversation.dart';

/// Repository for AI Coach operations.
class AiCoachRepository {
  final AiCoachRemoteDataSource _remote;

  AiCoachRepository(this._remote);

  /// Sends a message and returns the AI reply.
  Future<({ChatMessage? message, Failure? error})> chat(
    String message, {
    int? conversationId,
  }) async {
    try {
      final reply = await _remote.chat(message, conversationId: conversationId);
      return (message: reply, error: null);
    } on Failure catch (e) {
      return (message: null, error: e);
    } catch (e) {
      return (message: null, error: UnknownFailure(message: e.toString()));
    }
  }

  /// Fetches all conversations for the customer.
  Future<({List<Conversation>? conversations, Failure? error})>
      getConversations() async {
    try {
      final conversations = await _remote.getConversations();
      return (conversations: conversations, error: null);
    } on Failure catch (e) {
      return (conversations: null, error: e);
    } catch (e) {
      return (
        conversations: null,
        error: UnknownFailure(message: e.toString()),
      );
    }
  }

  /// Fetches the messages for a conversation.
  Future<({List<ChatMessage>? messages, Failure? error})> getMessages(
    int conversationId,
  ) async {
    try {
      final messages = await _remote.getMessages(conversationId);
      return (messages: messages, error: null);
    } on Failure catch (e) {
      return (messages: null, error: e);
    } catch (e) {
      return (messages: null, error: UnknownFailure(message: e.toString()));
    }
  }
}
