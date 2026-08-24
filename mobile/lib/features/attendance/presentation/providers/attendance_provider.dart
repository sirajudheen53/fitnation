import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/data/data_sources/api_client.dart';
import '../../../auth/presentation/providers/auth_notifier.dart';
import '../../data/data_sources/attendance_remote_data_source.dart';
import '../../data/models/attendance_record.dart';
import '../../domain/repositories/attendance_repository.dart';

/// Provides the AttendanceRemoteDataSource.
final attendanceRemoteDataSourceProvider =
    Provider<AttendanceRemoteDataSource>((ref) {
  final dio = ApiClient.getInstance();
  return AttendanceRemoteDataSource(dio);
});

/// Provides the AttendanceRepository.
final attendanceRepositoryProvider = Provider<AttendanceRepository>((ref) {
  final remote = ref.read(attendanceRemoteDataSourceProvider);
  return AttendanceRepository(remote);
});

/// Gets the current customer id from the auth state.
int? _currentCustomerId(Ref ref) {
  return ref.read(authProvider).user?.id;
}

/// Fetches the attendance history for the current customer.
final attendanceHistoryProvider =
    FutureProvider<List<AttendanceRecord>>((ref) async {
  final customerId = _currentCustomerId(ref);
  if (customerId == null) return const [];
  final repo = ref.read(attendanceRepositoryProvider);
  final result = await repo.getHistory(customerId);
  if (result.error != null) throw result.error!;
  return result.records;
});

/// State for QR check-in.
class CheckInState {
  final bool isLoading;
  final bool isSuccess;
  final String? errorMessage;
  final AttendanceRecord? record;

  const CheckInState({
    this.isLoading = false,
    this.isSuccess = false,
    this.errorMessage,
    this.record,
  });

  CheckInState copyWith({
    bool? isLoading,
    bool? isSuccess,
    String? errorMessage,
    AttendanceRecord? record,
  }) {
    return CheckInState(
      isLoading: isLoading ?? this.isLoading,
      isSuccess: isSuccess ?? this.isSuccess,
      errorMessage: errorMessage,
      record: record ?? this.record,
    );
  }
}

/// Notifier for QR check-in.
class CheckInNotifier extends StateNotifier<CheckInState> {
  final AttendanceRepository _repository;

  CheckInNotifier(this._repository) : super(const CheckInState());

  Future<bool> checkIn(String qrCode, {int? customerId}) async {
    state = state.copyWith(isLoading: true, errorMessage: null, isSuccess: false);
    final result = await _repository.checkIn(qrCode: qrCode, customerId: customerId);
    if (result.error != null) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: result.error!.message,
      );
      return false;
    }
    state = CheckInState(isLoading: false, isSuccess: true, record: result.record);
    return true;
  }

  void reset() {
    state = const CheckInState();
  }
}

/// Provides the CheckInNotifier.
final checkInProvider =
    StateNotifierProvider<CheckInNotifier, CheckInState>((ref) {
  return CheckInNotifier(ref.read(attendanceRepositoryProvider));
});
