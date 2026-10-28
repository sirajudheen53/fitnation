import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/data/data_sources/api_client.dart';
import '../../data/data_sources/attendance_remote_data_source.dart';
import '../../data/models/attendance_record_model.dart';
import '../../domain/repositories/attendance_repository.dart';

/// Load lifecycle of the customer's check-in state.
enum CheckInStatus { idle, loading, loaded, error }

/// State of the home check-in card (issue #95).
@immutable
class CheckInState {
  final CheckInStatus status;
  final CheckInSummary? summary;

  /// Populated when [status] is [CheckInStatus.error].
  final String? errorMessage;

  const CheckInState({
    this.status = CheckInStatus.idle,
    this.summary,
    this.errorMessage,
  });

  CheckInState copyWith({
    CheckInStatus? status,
    CheckInSummary? summary,
    String? errorMessage,
  }) {
    return CheckInState(
      status: status ?? this.status,
      summary: summary ?? this.summary,
      errorMessage: errorMessage,
    );
  }
}

/// Loads the customer's check-in state for the home card.
class CheckInNotifier extends StateNotifier<CheckInState> {
  final AttendanceRepository _repository;

  CheckInNotifier(this._repository) : super(const CheckInState());

  /// (Re)loads the check-in summary from the backend.
  Future<void> load() async {
    state = state.copyWith(status: CheckInStatus.loading, errorMessage: null);

    final result = await _repository.myCheckInSummary();

    if (result.error != null) {
      state = state.copyWith(
        status: CheckInStatus.error,
        errorMessage: result.error!.message,
      );
      return;
    }

    state = state.copyWith(
      status: CheckInStatus.loaded,
      summary: result.summary,
    );
  }
}

/// Provides the attendance remote data source.
final attendanceRemoteDataSourceProvider =
    Provider<AttendanceRemoteDataSource>((ref) {
  return AttendanceRemoteDataSource(ApiClient.getInstance());
});

/// Provides the attendance repository.
final attendanceRepositoryProvider = Provider<AttendanceRepository>((ref) {
  return AttendanceRepository(ref.read(attendanceRemoteDataSourceProvider));
});

/// Provides the customer's check-in state for the home card.
final checkInProvider =
    StateNotifierProvider<CheckInNotifier, CheckInState>((ref) {
  return CheckInNotifier(ref.read(attendanceRepositoryProvider));
});
