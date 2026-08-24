import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/data/data_sources/api_client.dart';
import '../../data/data_sources/feedback_remote_data_source.dart';
import '../../data/models/feedback.dart';
import '../../domain/repositories/feedback_repository.dart';

/// Provides the FeedbackRemoteDataSource.
final feedbackRemoteDataSourceProvider = Provider<FeedbackRemoteDataSource>((ref) {
  final dio = ApiClient.getInstance();
  return FeedbackRemoteDataSource(dio);
});

/// Provides the FeedbackRepository.
final feedbackRepositoryProvider = Provider<FeedbackRepository>((ref) {
  final remote = ref.read(feedbackRemoteDataSourceProvider);
  return FeedbackRepository(remote);
});

/// State for submitting feedback.
class FeedbackFormState {
  final bool isLoading;
  final bool isSuccess;
  final String? errorMessage;

  const FeedbackFormState({
    this.isLoading = false,
    this.isSuccess = false,
    this.errorMessage,
  });

  FeedbackFormState copyWith({
    bool? isLoading,
    bool? isSuccess,
    String? errorMessage,
  }) {
    return FeedbackFormState(
      isLoading: isLoading ?? this.isLoading,
      isSuccess: isSuccess ?? this.isSuccess,
      errorMessage: errorMessage,
    );
  }
}

/// Notifier for submitting feedback.
class FeedbackFormNotifier extends StateNotifier<FeedbackFormState> {
  final FeedbackRepository _repository;

  FeedbackFormNotifier(this._repository) : super(const FeedbackFormState());

  Future<bool> submit({
    required String message,
    String? subject,
    int? rating,
    String? category,
    int? customerId,
  }) async {
    state = state.copyWith(isLoading: true, errorMessage: null, isSuccess: false);

    final feedback = Feedback(
      customerId: customerId,
      subject: subject,
      message: message,
      rating: rating,
      category: category,
    );

    final result = await _repository.submitFeedback(feedback);
    if (result.error != null) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: result.error!.message,
      );
      return false;
    }
    state = const FeedbackFormState(isLoading: false, isSuccess: true);
    return true;
  }

  void reset() {
    state = const FeedbackFormState();
  }
}

/// Provides the FeedbackFormNotifier.
final feedbackFormProvider =
    StateNotifierProvider<FeedbackFormNotifier, FeedbackFormState>((ref) {
  return FeedbackFormNotifier(ref.read(feedbackRepositoryProvider));
});
