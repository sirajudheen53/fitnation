import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/data/data_sources/api_client.dart';
import '../../data/data_sources/membership_remote_data_source.dart';
import '../../data/models/membership_model.dart';
import '../../domain/repositories/membership_repository.dart';

/// Load lifecycle of the customer's membership state.
enum MembershipStatus { idle, loading, loaded, error }

/// State of the membership shown on the home dues card (issue #95).
@immutable
class MembershipState {
  final MembershipStatus status;
  final MembershipModel? membership;

  /// Populated when [status] is [MembershipStatus.error].
  final String? errorMessage;

  const MembershipState({
    this.status = MembershipStatus.idle,
    this.membership,
    this.errorMessage,
  });

  MembershipState copyWith({
    MembershipStatus? status,
    MembershipModel? membership,
    String? errorMessage,
  }) {
    return MembershipState(
      status: status ?? this.status,
      membership: membership ?? this.membership,
      errorMessage: errorMessage,
    );
  }
}

/// Loads the customer's current membership for the home card.
class MembershipNotifier extends StateNotifier<MembershipState> {
  final MembershipRepository _repository;

  MembershipNotifier(this._repository) : super(const MembershipState());

  /// (Re)loads the membership from the backend.
  Future<void> load() async {
    state = state.copyWith(
      status: MembershipStatus.loading,
      errorMessage: null,
    );

    final result = await _repository.currentMembership();

    if (result.error != null) {
      state = state.copyWith(
        status: MembershipStatus.error,
        errorMessage: result.error!.message,
      );
      return;
    }

    state = state.copyWith(
      status: MembershipStatus.loaded,
      membership: result.membership,
    );
  }
}

/// Provides the membership remote data source.
final membershipRemoteDataSourceProvider =
    Provider<MembershipRemoteDataSource>((ref) {
  return MembershipRemoteDataSource(ApiClient.getInstance());
});

/// Provides the membership repository.
final membershipRepositoryProvider = Provider<MembershipRepository>((ref) {
  return MembershipRepository(ref.read(membershipRemoteDataSourceProvider));
});

/// Provides the customer's current membership for the home card.
final membershipProvider =
    StateNotifierProvider<MembershipNotifier, MembershipState>((ref) {
  return MembershipNotifier(ref.read(membershipRepositoryProvider));
});
