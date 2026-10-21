import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/profile/data/data_sources/profile_remote_data_source.dart';
import '../../../helpers/canned_adapter.dart';

void main() {
  group('ProfileRemoteDataSource', () {
    test('getProfile GETs the customer by id', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'id': 5,
                'name': 'Asha Kumar',
                'email': 'asha@example.com',
                'is_active': true,
              }),
        ],
      );
      final source = ProfileRemoteDataSource(dio);

      final profile = await source.getProfile(5);

      expect(profile.id, 5);
      expect(profile.fullName, 'Asha Kumar');
      expect(
        (dio.httpClientAdapter as CannedAdapter).recorded.single.uri.path,
        '/customers/customers/5/',
      );
    });

    test('updateProfile PATCHes the given fields', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {'id': 5, 'phone': '+919999000001'}),
        ],
      );
      final source = ProfileRemoteDataSource(dio);

      final profile = await source.updateProfile(5, {'phone': '+919999000001'});

      expect(profile.phone, '+919999000001');
      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.method, 'PATCH');
      expect(call.recorded.single.bodyMap, {'phone': '+919999000001'});
    });

    test('updateHealthProfile PATCHes the health-profile route', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {'id': 2, 'height_cm': 171.5, 'weight_kg': 68.2}),
        ],
      );
      final source = ProfileRemoteDataSource(dio);

      final health = await source.updateHealthProfile(5, {'height': 171.5});

      expect(health.height, 171.5);
      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.method, 'PATCH');
      expect(call.recorded.single.uri.path, '/customers/customers/5/health-profile/');
    });

    test('getHealthProfile returns null on a 404 (no profile yet)', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(404, {'detail': 'Not found.'})],
      );
      final source = ProfileRemoteDataSource(dio);

      expect(await source.getHealthProfile(5), isNull);
    });

    test('getHealthProfile surfaces other errors', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(401, {'detail': 'Token expired'})],
      );
      final source = ProfileRemoteDataSource(dio);

      await expectLater(
        source.getHealthProfile(5),
        throwsA(
          isA<AuthFailure>().having((f) => f.message, 'message', 'Token expired'),
        ),
      );
    });

    test('getMemberships lists memberships per customer', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [
          () => cannedResponse(200, {
                'results': [
                  {
                    'id': 3,
                    'plan_name': 'Gold',
                    'status': 'active',
                    'price': 12000,
                    'end_date': '2027-01-01T00:00:00Z',
                  },
                ],
              }),
        ],
      );
      final source = ProfileRemoteDataSource(dio);

      final memberships = await source.getMemberships(5);

      expect(memberships, hasLength(1));
      expect(memberships.single.planName, 'Gold');
      expect(memberships.single.isActive, isTrue);

      final call = dio.httpClientAdapter as CannedAdapter;
      expect(call.recorded.single.uri.path, '/memberships/memberships/');
      expect(call.recorded.single.uri.queryParameters['customer'], '5');
    });

    test('validation errors carry the field map', () async {
      final dio = Dio();
      dio.httpClientAdapter = CannedAdapter(
        calls: [() => cannedResponse(400, {'phone': ['Bad phone number']})],
      );
      final source = ProfileRemoteDataSource(dio);

      await expectLater(
        source.updateProfile(5, {'phone': 'wrong'}),
        throwsA(
          isA<ValidationFailure>()
              .having((f) => f.errors, 'errors', {'phone': ['Bad phone number']}),
        ),
      );
    });
  });
}