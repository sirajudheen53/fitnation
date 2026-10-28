import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/memberships/presentation/providers/membership_providers.dart';

import '../../../../helpers/membership_fakes.dart';

void main() {
  late FakeMembershipRemoteDataSource remote;
  late ProviderContainer container;

  setUp(() {
    remote = FakeMembershipRemoteDataSource();
    container = ProviderContainer(
      overrides: [
        membershipRepositoryProvider
            .overrideWithValue(FakeMembershipRepository(remote)),
      ],
    );
  });

  tearDown(() => container.dispose());

  MembershipState state() => container.read(membershipProvider);

  test('starts idle before any load', () {
    expect(state().status, MembershipStatus.idle);
    expect(state().membership, isNull);
  });

  test('load transitions idle → loaded with the membership', () async {
    remote.membershipResult = [membership()];

    await container.read(membershipProvider.notifier).load();

    expect(state().status, MembershipStatus.loaded);
    expect(state().membership!.planName, 'Monthly');
    expect(state().errorMessage, isNull);
  });

  test('no memberships still lands in loaded with null', () async {
    await container.read(membershipProvider.notifier).load();

    expect(state().status, MembershipStatus.loaded);
    expect(state().membership, isNull);
  });

  test('load surfaces the failure message on error', () async {
    remote.membershipError = const AuthFailure(message: 'Not authorized');

    await container.read(membershipProvider.notifier).load();

    expect(state().status, MembershipStatus.error);
    expect(state().errorMessage, 'Not authorized');
    expect(state().membership, isNull);
  });

  test('a successful refresh replaces the membership', () async {
    remote.membershipResult = [membership()];
    await container.read(membershipProvider.notifier).load();

    remote.membershipResult = [membership(status: 'expired')];
    await container.read(membershipProvider.notifier).load();

    expect(state().status, MembershipStatus.loaded);
    expect(state().membership!.isActive, isFalse);
  });
}
