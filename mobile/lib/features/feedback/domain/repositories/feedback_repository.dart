import '../../../../core/errors/failures.dart';
import '../../data/data_sources/feedback_remote_data_source.dart';
import '../../data/models/feedback.dart';

/// Repository for feedback operations.
class FeedbackRepository {
  final FeedbackRemoteDataSource _remote;

  FeedbackRepository(this._remote);

  /// Submits feedback.
  Future<({Feedback? feedback, Failure? error})> submitFeedback(
    Feedback feedback,
  ) async {
    try {
      final created = await _remote.submitFeedback(feedback);
      return (feedback: created, error: null);
    } on Failure catch (e) {
      return (feedback: null, error: e);
    } catch (e) {
      return (feedback: null, error: UnknownFailure(message: e.toString()));
    }
  }

  /// Fetches the feedback submitted by a customer.
  Future<({List<Feedback> feedback, Failure? error})> getFeedback(
    int customerId,
  ) async {
    try {
      final feedback = await _remote.getFeedback(customerId);
      return (feedback: feedback, error: null);
    } on Failure catch (e) {
      return (feedback: const <Feedback>[], error: e);
    } catch (e) {
      return (feedback: const <Feedback>[], error: UnknownFailure(message: e.toString()));
    }
  }
}
