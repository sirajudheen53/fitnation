import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/data/data_sources/api_client.dart';
import '../../../auth/presentation/providers/auth_notifier.dart';
import '../../data/data_sources/profile_remote_data_source.dart';
import '../../data/models/customer_profile.dart';
import '../../domain/repositories/profile_repository.dart';

/// Provides the ProfileRemoteDataSource.
final profileRemoteDataSourceProvider = Provider<ProfileRemoteDataSource>((ref) {
  final dio = ApiClient.getInstance();
  return ProfileRemoteDataSource(dio);
});

/// Provides the ProfileRepository.
final profileRepositoryProvider = Provider<ProfileRepository>((ref) {
  final remote = ref.read(profileRemoteDataSourceProvider);
  return ProfileRepository(remote);
});

/// Gets the current customer id from the auth state.
int? _currentCustomerId(Ref ref) {
  return ref.read(authProvider).user?.id;
}

/// Fetches the customer profile for the current customer.
final customerProfileProvider = FutureProvider<CustomerProfile?>((ref) async {
  final customerId = _currentCustomerId(ref);
  if (customerId == null) return null;
  final repo = ref.read(profileRepositoryProvider);
  final result = await repo.getProfile(customerId);
  if (result.error != null) throw result.error!;
  return result.profile;
});

/// Fetches the health profile for the current customer.
final healthProfileProvider = FutureProvider<HealthProfile?>((ref) async {
  final customerId = _currentCustomerId(ref);
  if (customerId == null) return null;
  final repo = ref.read(profileRepositoryProvider);
  final result = await repo.getHealthProfile(customerId);
  if (result.error != null) throw result.error!;
  return result.health;
});

/// Fetches the memberships for the current customer.
final membershipsProvider = FutureProvider<List<Membership>>((ref) async {
  final customerId = _currentCustomerId(ref);
  if (customerId == null) return const [];
  final repo = ref.read(profileRepositoryProvider);
  final result = await repo.getMemberships(customerId);
  if (result.error != null) throw result.error!;
  return result.memberships;
});
