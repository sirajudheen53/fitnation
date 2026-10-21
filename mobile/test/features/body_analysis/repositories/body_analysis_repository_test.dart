import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/body_analysis/data/data_sources/body_analysis_remote_data_source.dart';
import 'package:fitnation_app/features/body_analysis/domain/repositories/body_analysis_repository.dart';
import '../../../helpers/canned_adapter.dart';

void main() {
  BodyAnalysisRepository repo(CannedAdapter adapter) {
    final dio = Dio()..httpClientAdapter = adapter;
    return BodyAnalysisRepository(BodyAnalysisRemoteDataSource(dio));
  }

  test('getAnalyses returns the list, or null with the failure', () async {
    final ok = repo(CannedAdapter(
      calls: [
        () => cannedResponse(200, {
              'results': [
                {'id': 1, 'bmi': 23.1, 'status': 'complete'},
              ],
            }),
      ],
    ));
    final (analyses: list, error: okError) = await ok.getAnalyses();
    expect(list!.single.bmi, 23.1);
    expect(okError, isNull);

    final down = repo(CannedAdapter(
      calls: [() => cannedResponse(500, {'detail': 'AI backend down'})],
    ));
    final (analyses: none, error: failError) = await down.getAnalyses();
    expect(none, isNull);
    expect(failError, isA<ServerFailure>().having((f) => f.statusCode, 'code', 500));
  });

  test('createAnalysis posts and returns the created analysis', () async {
    final ok = repo(CannedAdapter(
      calls: [() => cannedResponse(201, {'id': 4, 'status': 'pending'})],
    ));
    final (analysis: created, error: createError) =
        await ok.createAnalysis({'photo_id': 12});
    expect(created!.id, 4);
    expect(createError, isNull);

    final rejected = repo(CannedAdapter(
      calls: [() => cannedResponse(400, {'photo_id': ['Unknown photo']})],
    ));
    final (analysis: blocked, error: rejectError) =
        await rejected.createAnalysis({});
    expect(blocked, isNull);
    expect(rejectError, isA<ValidationFailure>());
  });

  test('uploadPhoto mints the multipart request and returns the photo', () async {
    final ok = repo(CannedAdapter(
      calls: [
        () => cannedResponse(201, {'id': 8, 'photo_type': 'back', 'status': 'uploaded'}),
      ],
    ));
    final dir = await Directory.systemTemp.createTemp('body-analysis-repo');
    addTearDown(() => dir.delete(recursive: true));
    File('${dir.path}/p.png').writeAsStringSync('\x89PNG');

    final (photo: photo, error: photoError) =
        await ok.uploadPhoto('${dir.path}/p.png', 'back');
    expect(photo!.id, 8);
    expect(photoError, isNull);

    final tooBig = repo(CannedAdapter(
      calls: [() => cannedResponse(413, {'detail': 'File too large'})],
    ));
    final (photo: refused, error: refusedError) =
        await tooBig.uploadPhoto('${dir.path}/p.png', 'front');
    expect(refused, isNull);
    expect(refusedError, isA<ServerFailure>());
  });

  test('getProgress returns the logs, or the failure', () async {
    final ok = repo(CannedAdapter(
      calls: [
        () => cannedResponse(200, [
              {'id': 1, 'weight': 71.0, 'logged_at': '2026-05-01T00:00:00Z'},
            ]),
      ],
    ));
    final (logs: logs, error: okError) = await ok.getProgress();
    expect(logs!.single.weight, 71.0);
    expect(okError, isNull);

    final down = repo(CannedAdapter(
      calls: [() => cannedResponse(500, {'detail': 'x'})],
    ));
    final (logs: none, error: failError) = await down.getProgress();
    expect(none, isNull);
    expect(failError, isA<ServerFailure>());
  });
}