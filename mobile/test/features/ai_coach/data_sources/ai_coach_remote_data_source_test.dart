import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/ai_coach/data/data_sources/ai_coach_remote_data_source.dart';
import '../../../helpers/canned_adapter.dart';

void main() {
  group('AiCoachRemoteDataSource.chat', () {
    test('POSTs the message and starts a new conversation when no id given', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'id': 1,
                'content': 'Here is your plan for today.',
                'sender': 'ai',
                'recommendation': 'Focus on protein',
              }),
        ],
      );
      final source = AiCoachRemoteDataSource(dio);

      final reply = await source.chat('What should I eat today?');

      expect(reply.content, 'Here is your plan for today.');
      expect(reply.isUser, isFalse);
      expect(reply.recommendation, 'Focus on protein');

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.method, 'POST');
      expect(call.recorded.single.uri.path, '/ai/coach/chat/');
      expect(call.recorded.single.bodyMap, {'message': 'What should I eat today?'});
    });

    test('sends the conversation id when continuing a thread', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {'id': 2, 'is_user': false, 'content': 'ok'}),
        ],
      );
      final source = AiCoachRemoteDataSource(dio);

      await source.chat('more', conversationId: 7);

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.bodyMap, {'message': 'more', 'conversation_id': 7});
    });

    test('marks user-authored replies coming back as user messages', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(200, {'id': 3, 'sender': 'user'})],
      );

      final reply = await AiCoachRemoteDataSource(dio).chat('echo');

      expect(reply.isUser, isTrue);
    });
  });

  group('AiCoachRemoteDataSource.getConversations', () {
    test('GETs conversations and parses pages', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'results': [
                  {
                    'id': 4,
                    'title': 'Training questions',
                    'message_count': 9,
                    'last_message_at': '2026-06-01T10:00:00Z',
                  },
                ],
              }),
        ],
      );
      final source = AiCoachRemoteDataSource(dio);

      final conversations = await source.getConversations();

      expect(conversations, hasLength(1));
      expect(conversations.single.id, 4);
      expect(conversations.single.messageCount, 9);
      expect(
        (dio.httpClientAdapter as CannedAdapter).recorded.single.uri.path,
        '/ai/coach/conversations/',
      );
    });
  });

  group('AiCoachRemoteDataSource.getMessages', () {
    test('GETs the conversation route with the id substituted into the path', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'results': [
                  {'id': 1, 'sender': 'user', 'content': 'hello'},
                ],
              }),
        ],
      );
      final source = AiCoachRemoteDataSource(dio);

      final messages = await source.getMessages(7);

      expect(messages.single.isUser, isTrue);
      expect(messages.single.content, 'hello');

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.method, 'GET');
      // The backend route is conversations/<int>/messages/ — the {id}
      // placeholder must be substituted, and no stray query param sent.
      expect(call.recorded.single.uri.path, '/ai/coach/conversations/7/messages/');
      expect(call.recorded.single.uri.queryParameters, isEmpty);
    });

    test('a failed send maps to a failure, not a DioException', () async {
      final dio = Dio()..httpClientAdapter = CannedAdapter(
        throws: () => DioException(
          requestOptions: RequestOptions(path: '/x'),
          type: DioExceptionType.connectionError,
        ),
      );

      await expectLater(
        AiCoachRemoteDataSource(dio).chat('hi'),
        throwsA(isA<NetworkFailure>()),
      );
    });
  });
}