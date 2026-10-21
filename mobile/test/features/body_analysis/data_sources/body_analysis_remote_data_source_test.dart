import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/body_analysis/data/data_sources/body_analysis_remote_data_source.dart';
import '../../../helpers/canned_adapter.dart';

void main() {
  group('BodyAnalysisRemoteDataSource', () {
    test('getAnalyses GETs the analyses endpoint and parses pages', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'results': [
                  {
                    'id': 1,
                    'analyzed_at': '2026-05-20T12:00:00Z',
                    'bmi': 23.1,
                    'body_fat_percentage': 19.0,
                    'posture_score': 8.5,
                    'weight': 72.0,
                    'height': 175.0,
                    'status': 'complete',
                    'notes': 'good posture',
                  },
                ],
              }),
        ],
      );
      final source = BodyAnalysisRemoteDataSource(dio);

      final analyses = await source.getAnalyses();

      expect(analyses, hasLength(1));
      expect(analyses.single.bmi, 23.1);
      expect(analyses.single.postureScore, 8.5);
      expect(analyses.single.status, 'complete');
      expect(
        (dio.httpClientAdapter as CannedAdapter).recorded.single.method,
        'GET',
      );
      expect(
        (dio.httpClientAdapter as CannedAdapter).recorded.single.uri.path,
        '/ai/body/analyses/',
      );
    });

    test('createAnalysis POSTs the payload and parses the created analysis', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(201, {
                'id': 4,
                'weight': 70.0,
                'height': 174.0,
                'status': 'pending',
              }),
        ],
      );
      final source = BodyAnalysisRemoteDataSource(dio);

      final analysis = await source.createAnalysis({'photo_id': 12});

      expect(analysis.id, 4);
      expect(analysis.status, 'pending');
      expect(analysis.weight, 70.0);

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.method, 'POST');
      expect(call.recorded.single.bodyMap, {'photo_id': 12});
    });

    test('uploadPhoto posts a multipart body with the photo and type', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(201, {
                'id': 8,
                'url': 'https://cdn.example.com/back.png',
                'photo_type': 'back',
                'status': 'uploaded',
              }),
        ],
      );
      final source = BodyAnalysisRemoteDataSource(dio);
      final dir = await Directory.systemTemp.createTemp('body-analysis-test');
      final file = File('${dir.path}/photo.png')..writeAsStringSync('\x89PNG');
      addTearDown(() => dir.delete(recursive: true));

      final photo = await source.uploadPhoto(file.path, 'back');

      expect(photo.id, 8);
      expect(photo.photoType, 'back');
      expect(photo.url, 'https://cdn.example.com/back.png');

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.method, 'POST');
      expect(call.recorded.single.uri.path, '/ai/body/analyses/upload/');
      final form = call.recorded.single.body as FormData;
      expect(
        form.fields.any((f) => f.key == 'photo_type' && f.value == 'back'),
        isTrue,
      );
      expect(form.files.map((f) => f.key), contains('photo'));
    });

    test('getProgress parses weight logs with the zero-weight default', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, [
                {
                  'id': 1,
                  'logged_at': '2026-05-01T00:00:00Z',
                  'weight': 71.0,
                  'muscle_mass': 52.0,
                },
                {'id': 2},
              ]),
        ],
      );
      final source = BodyAnalysisRemoteDataSource(dio);

      final logs = await source.getProgress();

      expect(logs, hasLength(2));
      expect(logs.first.weight, 71.0);
      expect(logs.last.weight, 0);
      expect(logs.last.muscleMass, isNull);
    });

    test('errors map to the matching failures', () async {
      final connection = Dio()..httpClientAdapter = CannedAdapter(
        throws: () => DioException(
          requestOptions: RequestOptions(path: '/x'),
          type: DioExceptionType.connectionTimeout,
        ),
      );
      await expectLater(
        BodyAnalysisRemoteDataSource(connection).getAnalyses(),
        throwsA(isA<NetworkFailure>()),
      );

      final forbidden = Dio()..httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(403, {'detail': 'No access'})],
      );
      await expectLater(
        BodyAnalysisRemoteDataSource(forbidden).createAnalysis({}),
        throwsA(
          isA<AuthFailure>()
              .having((f) => f.statusCode, 'statusCode', 403)
              .having((f) => f.message, 'message', 'No access'),
        ),
      );

      final server = Dio()..httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(502, {'detail': 'AI backend down'})],
      );
      await expectLater(
        BodyAnalysisRemoteDataSource(server).getProgress(),
        throwsA(
          isA<ServerFailure>()
              .having((f) => f.statusCode, 'statusCode', 502)
              .having((f) => f.message, 'message', 'AI backend down'),
        ),
      );
    });
  });
}