import '../../../../core/errors/failures.dart';
import '../../data/data_sources/profile_remote_data_source.dart';
import '../../data/models/customer_profile.dart';

/// Repository for profile-related operations.
class ProfileRepository {
  final ProfileRemoteDataSource _remote;

  ProfileRepository(this._remote);

  /// Fetches the customer profile.
  Future<({CustomerProfile? profile, Failure? error})> getProfile(
    int customerId,
  ) async {
    try {
      final profile = await _remote.getProfile(customerId);
      return (profile: profile, error: null);
    } on Failure catch (e) {
      return (profile: null, error: e);
    } catch (e) {
      return (profile: null, error: UnknownFailure(message: e.toString()));
    }
  }

  /// Fetches the health profile for a customer.
  Future<({HealthProfile? health, Failure? error})> getHealthProfile(
    int customerId,
  ) async {
    try {
      final health = await _remote.getHealthProfile(customerId);
      return (health: health, error: null);
    } on Failure catch (e) {
      return (health: null, error: e);
    } catch (e) {
      return (health: null, error: UnknownFailure(message: e.toString()));
    }
  }

  /// Fetches the memberships for a customer.
  Future<({List<Membership> memberships, Failure? error})> getMemberships(
    int customerId,
  ) async {
    try {
      final memberships = await _remote.getMemberships(customerId);
      return (memberships: memberships, error: null);
    } on Failure catch (e) {
      return (memberships: const <Membership>[], error: e);
    } catch (e) {
      return (memberships: const <Membership>[], error: UnknownFailure(message: e.toString()));
    }
  }
}
