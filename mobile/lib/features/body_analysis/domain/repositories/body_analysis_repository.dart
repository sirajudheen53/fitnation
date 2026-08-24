import '../../../../core/errors/failures.dart';
import '../../data/data_sources/body_analysis_remote_data_source.dart';
import '../../models/body_analysis.dart';
import '../../models/body_photo.dart';
import '../../models/progress_log.dart';

/// Repository for Body Analysis operations.
class BodyAnalysisRepository {
  final BodyAnalysisRemoteDataSource _remote;

  BodyAnalysisRepository(this._remote);

  /// Fetches past body analyses.
  Future<({List<BodyAnalysis>? analyses, Failure? error})>
      getAnalyses() async {
    try {
      final analyses = await _remote.getAnalyses();
      return (analyses: analyses, error: null);
    } on Failure catch (e) {
      return (analyses: null, error: e);
    } catch (e) {
      return (analyses: null, error: UnknownFailure(message: e.toString()));
    }
  }

  /// Creates a new analysis.
  Future<({BodyAnalysis? analysis, Failure? error})> createAnalysis(
    Map<String, dynamic> data,
  ) async {
    try {
      final analysis = await _remote.createAnalysis(data);
      return (analysis: analysis, error: null);
    } on Failure catch (e) {
      return (analysis: null, error: e);
    } catch (e) {
      return (analysis: null, error: UnknownFailure(message: e.toString()));
    }
  }

  /// Uploads a photo for analysis.
  Future<({BodyPhoto? photo, Failure? error})> uploadPhoto(
    String filePath,
    String type,
  ) async {
    try {
      final photo = await _remote.uploadPhoto(filePath, type);
      return (photo: photo, error: null);
    } on Failure catch (e) {
      return (photo: null, error: e);
    } catch (e) {
      return (photo: null, error: UnknownFailure(message: e.toString()));
    }
  }

  /// Fetches weight-over-time progress.
  Future<({List<ProgressLog>? logs, Failure? error})> getProgress() async {
    try {
      final logs = await _remote.getProgress();
      return (logs: logs, error: null);
    } on Failure catch (e) {
      return (logs: null, error: e);
    } catch (e) {
      return (logs: null, error: UnknownFailure(message: e.toString()));
    }
  }
}
