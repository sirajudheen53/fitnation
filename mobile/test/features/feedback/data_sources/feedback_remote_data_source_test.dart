import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/feedback/data/data_sources/feedback_remote_data_source.dart';
import 'package:fitnation_app/features/feedback/data/models/feedback.dart';
import '../../../helpers/canned_adapter.dart';

void main() {
  group('FeedbackRemoteDataSource.submitFeedback', () {
    test('POSTs the feedback payload and parses the response', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(201, {
                'id': 8,
                'customer': 10,
                'subject': 'Great coach',
                'message': 'Sessions are on point',
                'rating': 5,
                'category': 'training',
                'submitted_at': '2026-06-01T10:00:00Z',
                'status': 'new',
              }),
        ],
      );
      final source = FeedbackRemoteDataSource(dio);

      final submitted = await source.submitFeedback(
        const Feedback(customerId: 10, message: 'Sessions are on point', rating: 5),
      );

      expect(submitted.id, 8);
      expect(submitted.status, 'new');
      expect(submitted.submittedAt, DateTime.parse('2026-06-01T10:00:00Z'));
      expect(submitted.rating, 5);

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.method, 'POST');
      expect(call.recorded.single.uri.path, '/feedback/feedback/');
      expect(call.recorded.single.bodyMap, {'customer': 10, 'message': 'Sessions are on point', 'rating': 5});
    });
  });

  group('FeedbackRemoteDataSource.getFeedback', () {
    test('GETs feedback filtered by customer', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, [
                {'id': 1, 'message': 'Great!', 'customer_id': 10, 'rating': 4},
                {'id': 2, 'customer_id': 10},
              ]),
        ],
      );
      final source = FeedbackRemoteDataSource(dio);

      final feedback = await source.getFeedback(10);

      expect(feedback, hasLength(2));
      expect(feedback.first.customerId, 10);
      expect(feedback.first.message, 'Great!');
      expect(feedback.last.message, '');

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.uri.path, '/feedback/feedback/');
      expect(call.recorded.single.uri.queryParameters['customer'], '10');
    });

    test('errors map to the failure ladder', () async {
      final network = Dio()..httpClientAdapter = CannedAdapter(
        throws: () => DioException(
          requestOptions: RequestOptions(path: '/x'),
          type: DioExceptionType.receiveTimeout,
        ),
      );
      final networkSource = FeedbackRemoteDataSource(network);
      await expectLater(
        networkSource.getFeedback(1),
        throwsA(isA<NetworkFailure>()),
      );

      final auth = Dio()..httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(401, {'detail': 'Token stale'})],
      );
      await expectLater(
        FeedbackRemoteDataSource(auth).submitFeedback(const Feedback(message: 'hi')),
        throwsA(
          isA<AuthFailure>().having((f) => f.message, 'message', 'Token stale'),
        ),
      );

      final unknown = Dio()..httpClientAdapter = CannedAdapter(
        throws: () => DioException(
          requestOptions: RequestOptions(path: '/x'),
          type: DioExceptionType.badCertificate,
          message: 'bad cert',
        ),
      );
      await expectLater(
        FeedbackRemoteDataSource(unknown).getFeedback(1),
        throwsA(isA<UnknownFailure>()),
      );
    });
  });
}