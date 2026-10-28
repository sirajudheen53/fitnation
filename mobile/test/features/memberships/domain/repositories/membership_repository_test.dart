import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/memberships/domain/repositories/membership_repository.dart';

import '../../../../helpers/fakes.dart';
import '../../../../helpers/membership_fakes.dart';

void main() {
  late FakeMembershipRemoteDataSource remote;
  late MembershipRepository repository;

  setUp(() {
    remote = FakeMembershipRemoteDataSource();
    repository = MembershipRepository(remote);
  });

  test('returns the active membership on success', () async {
    remote.membershipResult = [membership()];

    final result = await repository.currentMembership();

    expect(result.error, isNull);
    expect(result.membership!.isActive, isTrue);
  });

  test('no memberships yields null, not an error', () async {
    final result = await repository.currentMembership();

    expect(result.error, isNull);
    expect(result.membership, isNull);
  });

  test('a Failure from the data source becomes the error', () async {
    remote.membershipError = const AuthFailure(message: 'Not authorized');

    final result = await repository.currentMembership();

    expectFailure(result.error, AuthFailure, messageContains: 'Not authorized');
    expect(result.membership, isNull);
  });

  test('an unexpected error becomes an UnknownFailure', () async {
    remote.membershipError = Exception('boom');

    final result = await repository.currentMembership();

    expectFailure(result.error, UnknownFailure);
    expect(result.membership, isNull);
  });
}
