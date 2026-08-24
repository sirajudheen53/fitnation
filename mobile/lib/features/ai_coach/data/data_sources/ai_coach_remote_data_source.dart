import 'package:dio/dio.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/failures.dart';
import '../../models/chat_message.dart';
import '../../models/conversation.dart';

/// Remote data source for the AI Coach.
class AiCoachRemoteDataSource {
  final Dio _dio;

  AiCoachRemoteDataSource(this._dio);

  /// Sends a message to the AI Coach and returns the AI reply.
  ///
  /// POST /api/v1/ai/coach/chat/
  Future<ChatMessage> chat(String message, {int? conversationId}) async {
    try {
      final response = await _dio.post(
        AppConstants.aiCoachChatEndpoint,
        data: {
          'message': message,
          if (conversationId != null) 'conversation_id': conversationId,
        },
      );
      return ChatMessage.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Fetches the list of conversations for the customer.
  ///
  /// GET /api/v1/ai/coach/conversations/
  Future<List<Conversation>> getConversations() async {
    try {
      final response = await _dio.get(
        AppConstants.aiCoachConversationsEndpoint,
      );
      final results = _extractResults(response.data);
      return results
          .map((e) => Conversation.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Fetches the messages of a conversation.
  ///
  /// GET /api/v1/ai/coach/messages/?conversation={id}
  Future<List<ChatMessage>> getMessages(int conversationId) async {
    try {
      final response = await _dio.get(
        AppConstants.aiCoachMessagesEndpoint,
        queryParameters: {'conversation': conversationId},
      );
      final results = _extractResults(response.data);
      return results
          .map((e) => ChatMessage.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  /// Extracts a list of results from a paginated or plain list response.
  List<dynamic> _extractResults(dynamic data) {
    if (data is List) return data;
    if (data is Map && data['results'] is List) {
      return data['results'] as List;
    }
    return const [];
  }

  /// Maps a DioException to a Failure.
  Failure _mapDioError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.connectionError:
        return const NetworkFailure();
      case DioExceptionType.badResponse:
        final statusCode = e.response?.statusCode;
        final data = e.response?.data;
        if (statusCode == 401 || statusCode == 403) {
          final message =
              (data is Map ? data['detail'] : null) ?? 'Authentication failed';
          return AuthFailure(message: message.toString(), statusCode: statusCode);
        }
        if (statusCode == 400 && data is Map<String, dynamic>) {
          return ValidationFailure(
            message: 'Validation error',
            errors: data,
            statusCode: statusCode,
          );
        }
        final message =
            (data is Map ? data['detail'] : null) ?? 'Server error';
        return ServerFailure(message: message.toString(), statusCode: statusCode);
      case DioExceptionType.cancel:
      case DioExceptionType.badCertificate:
      case DioExceptionType.transformTimeout:
      case DioExceptionType.unknown:
        return UnknownFailure(message: e.message ?? 'Unknown error');
    }
  }
}
