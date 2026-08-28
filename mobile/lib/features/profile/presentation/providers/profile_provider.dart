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

/// State for profile editing.
class ProfileEditState {
  final bool isSaving;
  final bool isSuccess;
  final String? errorMessage;

  const ProfileEditState({
    this.isSaving = false,
    this.isSuccess = false,
    this.errorMessage,
  });

  ProfileEditState copyWith({
    bool? isSaving,
    bool? isSuccess,
    String? errorMessage,
  }) {
    return ProfileEditState(
      isSaving: isSaving ?? this.isSaving,
      isSuccess: isSuccess ?? this.isSuccess,
      errorMessage: errorMessage,
    );
  }
}

/// Notifier for updating the customer profile and health profile.
class ProfileEditNotifier extends StateNotifier<ProfileEditState> {
  final ProfileRepository _repository;

  ProfileEditNotifier(this._repository) : super(const ProfileEditState());

  /// Updates the customer profile and returns whether it succeeded.
  Future<bool> updateProfile(int customerId, Map<String, dynamic> data) async {
    state = state.copyWith(isSaving: true, isSuccess: false, errorMessage: null);
    final result = await _repository.updateProfile(customerId, data);
    if (result.error != null) {
      state = state.copyWith(
        isSaving: false,
        errorMessage: result.error!.message,
      );
      return false;
    }
    state = const ProfileEditState(isSaving: false, isSuccess: true);
    return true;
  }

  /// Updates the health profile and returns whether it succeeded.
  Future<bool> updateHealthProfile(
    int customerId,
    Map<String, dynamic> data,
  ) async {
    state = state.copyWith(isSaving: true, isSuccess: false, errorMessage: null);
    final result = await _repository.updateHealthProfile(customerId, data);
    if (result.error != null) {
      state = state.copyWith(
        isSaving: false,
        errorMessage: result.error!.message,
      );
      return false;
    }
    state = const ProfileEditState(isSaving: false, isSuccess: true);
    return true;
  }

  void reset() {
    state = const ProfileEditState();
  }
}

/// Provides the ProfileEditNotifier.
final profileEditProvider =
    StateNotifierProvider<ProfileEditNotifier, ProfileEditState>((ref) {
  return ProfileEditNotifier(ref.read(profileRepositoryProvider));
});
