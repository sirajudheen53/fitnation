import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/profile/data/data_sources/profile_remote_data_source.dart';
import 'package:fitnation_app/features/profile/domain/repositories/profile_repository.dart';
import '../../../helpers/canned_adapter.dart';

void main() {
  ProfileRepository repo(CannedAdapter adapter) {
    final dio = Dio()..httpClientAdapter = adapter;
    return ProfileRepository(ProfileRemoteDataSource(dio));
  }

  group('ProfileRepository', () {
    test('getProfile returns the profile on success', () async {
      final repo1 = repo(CannedAdapter(
        calls: [() => cannedResponse(200, {'id': 5, 'name': 'Asha Kumar'})],
      ));
      final (:profile, :error) = await repo1.getProfile(5);

      expect(profile!.name, 'Asha Kumar');
      expect(error, isNull);
    });

    test('getProfile returns the failure when the server is down', () async {
      final repo1 = repo(CannedAdapter(
        calls: [() => cannedResponse(500, {'detail': 'DB down'})],
      ));
      final (:profile, :error) = await repo1.getProfile(5);

      expect(profile, isNull);
      expect(error, isA<ServerFailure>().having((f) => f.statusCode, 'code', 500));
    });

    test('updateProfile passes the payload through', () async {
      final repo1 = repo(CannedAdapter(
        calls: [() => cannedResponse(200, {'id': 5, 'phone': '+919999000001'})],
      ));
      final (:profile, :error) =
          await repo1.updateProfile(5, {'phone': '+919999000001'});

      expect(profile!.phone, '+919999000001');
      expect(error, isNull);
    });

    test('updateProfile surfaces validation failures', () async {
      final repo1 = repo(CannedAdapter(
        calls: [() => cannedResponse(400, {'email': ['Invalid email']})],
      ));
      final (:profile, :error) = await repo1.updateProfile(5, {'email': 'bad'});

      expect(profile, isNull);
      expect(error, isA<ValidationFailure>());
    });

    test('updateHealthProfile returns the health data', () async {
      final repo1 = repo(CannedAdapter(
        calls: [() => cannedResponse(200, {'id': 2, 'weight_kg': 68.2})],
      ));
      final (:health, :error) =
          await repo1.updateHealthProfile(5, {'weight': 68.2});

      expect(health!.weight, 68.2);
      expect(error, isNull);
    });

    test('getHealthProfile yields null health without an error on 404', () async {
      final repo1 = repo(CannedAdapter(
        calls: [() => cannedResponse(404, {'detail': 'Not found.'})],
      ));
      final (:health, :error) = await repo1.getHealthProfile(5);

      expect(health, isNull);
      expect(error, isNull);
    });

    test('getMemberships returns the list, or the failure', () async {
      final ok = repo(CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'results': [
                  {'id': 3, 'plan_name': 'Gold', 'status': 'active'},
                ],
              }),
        ],
      ));
      final (:memberships, error: okError) = await ok.getMemberships(5);
      expect(memberships.single.planName, 'Gold');
      expect(okError, isNull);

      final down = repo(CannedAdapter(
        calls: [() => cannedResponse(503, {'detail': 'read-only'})],
      ));
      final (memberships: failedList, error: failError) =
          await down.getMemberships(5);
      expect(failedList, isEmpty);
      expect(failError, isA<ServerFailure>());
    });
  });
}