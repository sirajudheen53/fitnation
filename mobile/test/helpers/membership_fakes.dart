import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/memberships/data/data_sources/membership_remote_data_source.dart';
import 'package:fitnation_app/features/memberships/data/models/membership_model.dart';
import 'package:fitnation_app/features/memberships/domain/repositories/membership_repository.dart';

/// Canned membership row shared across membership tests.
MembershipModel membership({
  int id = 3,
  String status = 'active',
  String planName = 'Monthly',
}) =>
    MembershipModel(
      id: id,
      plan: 2,
      planName: planName,
      price: 1500,
      startDate: DateTime(2026, 10, 1),
      endDate: DateTime(2026, 11, 1),
      status: status,
    );

/// Recording fake for [MembershipRemoteDataSource].
class FakeMembershipRemoteDataSource implements MembershipRemoteDataSource {
  List<MembershipModel> membershipResult = const [];
  Object? membershipError;
  int membershipCalls = 0;

  @override
  Future<List<MembershipModel>> fetchMyMemberships() async {
    membershipCalls++;
    final error = membershipError;
    if (error != null) throw error;
    return membershipResult;
  }
}

/// Repository fake backed by [FakeMembershipRemoteDataSource], mirroring
/// the real repository's Failure-to-record conversion.
class FakeMembershipRepository implements MembershipRepository {
  FakeMembershipRepository(this._remote);

  final FakeMembershipRemoteDataSource _remote;

  @override
  Future<({MembershipModel? membership, Failure? error})>
      currentMembership() async {
    try {
      final memberships = await _remote.fetchMyMemberships();
      return (
        membership: MembershipModel.pickCurrent(memberships),
        error: null,
      );
    } on Failure catch (e) {
      return (membership: null, error: e);
    }
  }
}
