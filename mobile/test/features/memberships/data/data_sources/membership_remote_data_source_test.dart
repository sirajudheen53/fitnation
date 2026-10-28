import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/memberships/data/data_sources/membership_remote_data_source.dart';

import '../../../../helpers/fakes.dart';

void main() {
  Map<String, dynamic> membershipRow({int id = 3, String status = 'active'}) => {
        'id': id,
        'customer': 5,
        'customer_id': 5,
        'customer_name': 'Arjun Nair',
        'customer_is_deleted': false,
        'plan': 2,
        'plan_name': 'Monthly',
        'price': 1500.0,
        'start_date': '2026-10-01',
        'end_date': '2026-11-01',
        'status': status,
        'auto_renew': false,
        'created_at': '2026-10-01T09:00:00Z',
        'updated_at': '2026-10-01T09:00:00Z',
      };

  test('fetchMyMemberships GETs the memberships list and parses the page',
      () async {
    final requests = <RequestOptions>[];
    final adapter = FakeDioAdapter((options) {
      requests.add(options);
      return FakeDioAdapter.json({
        'count': 2,
        'next': null,
        'previous': null,
        'results': [
          membershipRow(id: 3),
          membershipRow(id: 4, status: 'expired'),
        ],
      });
    });
    final source = MembershipRemoteDataSource(FakeDioAdapter.client(adapter));

    final memberships = await source.fetchMyMemberships();

    expect(memberships, hasLength(2));
    expect(memberships.first.planName, 'Monthly');
    expect(memberships.first.status, 'active');
    expect(requests.single.method, 'GET');
    expect(requests.single.path, '/memberships/memberships/');
    expect(requests.single.queryParameters, isEmpty);
  });

  test('a 403 surfaces as an AuthFailure', () async {
    final adapter = FakeDioAdapter(
        (options) => FakeDioAdapter.json({'detail': 'Nope'}, 403));
    final source = MembershipRemoteDataSource(FakeDioAdapter.client(adapter));

    await expectLater(
      source.fetchMyMemberships(),
      throwsA(isA<AuthFailure>()),
    );
  });
}
