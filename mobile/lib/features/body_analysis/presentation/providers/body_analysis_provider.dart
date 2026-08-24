import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/data/data_sources/api_client.dart';
import '../../data/data_sources/body_analysis_remote_data_source.dart';
import '../../domain/repositories/body_analysis_repository.dart';
import '../../models/body_analysis.dart';
import '../../models/progress_log.dart';

/// Provides the BodyAnalysisRemoteDataSource.
final bodyAnalysisRemoteDataSourceProvider =
    Provider<BodyAnalysisRemoteDataSource>((ref) {
  final dio = ApiClient.getInstance();
  return BodyAnalysisRemoteDataSource(dio);
});

/// Provides the BodyAnalysisRepository.
final bodyAnalysisRepositoryProvider = Provider<BodyAnalysisRepository>((ref) {
  final remote = ref.read(bodyAnalysisRemoteDataSourceProvider);
  return BodyAnalysisRepository(remote);
});

/// Fetches past body analyses for the current customer.
final bodyAnalysesProvider = FutureProvider<List<BodyAnalysis>>((ref) async {
  final repo = ref.read(bodyAnalysisRepositoryProvider);
  final result = await repo.getAnalyses();
  if (result.error != null) throw result.error!;
  return result.analyses ?? const [];
});

/// Fetches weight-over-time progress logs.
final bodyProgressProvider = FutureProvider<List<ProgressLog>>((ref) async {
  final repo = ref.read(bodyAnalysisRepositoryProvider);
  final result = await repo.getProgress();
  if (result.error != null) throw result.error!;
  return result.logs ?? const [];
});

/// State for uploading a photo.
class UploadState {
  final bool isLoading;
  final bool isSuccess;
  final String? errorMessage;

  const UploadState({
    this.isLoading = false,
    this.isSuccess = false,
    this.errorMessage,
  });

  UploadState copyWith({
    bool? isLoading,
    bool? isSuccess,
    String? errorMessage,
  }) {
    return UploadState(
      isLoading: isLoading ?? this.isLoading,
      isSuccess: isSuccess ?? this.isSuccess,
      errorMessage: errorMessage,
    );
  }
}

/// Notifier handling photo upload.
class UploadNotifier extends StateNotifier<UploadState> {
  final BodyAnalysisRepository _repository;

  UploadNotifier(this._repository) : super(const UploadState());

  /// Uploads a photo and creates an analysis.
  Future<bool> upload(String filePath, String type) async {
    state = state.copyWith(isLoading: true, errorMessage: null, isSuccess: false);
    final result = await _repository.uploadPhoto(filePath, type);
    if (result.error != null) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: result.error!.message,
      );
      return false;
    }
    state = const UploadState(isLoading: false, isSuccess: true);
    return true;
  }

  void reset() {
    state = const UploadState();
  }
}

/// Provides the UploadNotifier.
final uploadProvider =
    StateNotifierProvider<UploadNotifier, UploadState>((ref) {
  return UploadNotifier(ref.read(bodyAnalysisRepositoryProvider));
});
