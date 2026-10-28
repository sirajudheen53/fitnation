import '../../../../core/errors/failures.dart';
import '../../data/data_sources/membership_remote_data_source.dart';
import '../../data/models/membership_model.dart';

/// Repository for the logged-in customer's membership state (issue #95).
class MembershipRepository {
  final MembershipRemoteDataSource _remote;

  MembershipRepository(this._remote);

  /// The membership the home card should show (active preferred).
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
    } catch (e) {
      return (membership: null, error: UnknownFailure(message: e.toString()));
    }
  }
}
