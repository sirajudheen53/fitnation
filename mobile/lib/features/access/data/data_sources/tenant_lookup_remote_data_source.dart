import 'package:dio/dio.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/errors/failures.dart';

/// A gym resolved from a member-entered gym code.
class GymLookup {
  const GymLookup({required this.uuid, required this.name});

  /// Tenant UUID of the gym (the anchor to pin the login to).
  final String uuid;

  /// Gym display name, shown to the member to confirm the match.
  final String name;

  @override
  String toString() => 'GymLookup($name, $uuid)';
}

/// Remote data source for the unauthenticated gym-code lookup
/// (`GET /api/v1/tenants/lookup/?code=CODE`, FBOS-011 §7.1).
///
/// Members who install the app from a raw Play search have no invite link
/// and therefore no anchor. They can type the gym code printed at the front
/// desk; this endpoint turns that code into the tenant anchor.
class TenantLookupRemoteDataSource {
  final Dio _dio;

  TenantLookupRemoteDataSource(this._dio);

  /// Looks up the gym for [code].
  ///
  /// Throws a [Failure] on any error: an unknown code comes back as a 404
  /// and is surfaced as a [ServerFailure] with the backend's generic
  /// "Gym not found." detail, so the screen can show a friendly message
  /// instead of crashing.
  Future<GymLookup> lookupByCode(String code) async {
    try {
      final response = await _dio.get(
        AppConstants.tenantLookupEndpoint,
        queryParameters: {'code': code},
      );
      final data = response.data;
      if (data is! Map<String, dynamic>) {
        throw const ServerFailure(message: 'Gym not found.');
      }
      final uuid = data['uuid'] as String?;
      final name = data['name'] as String?;
      if (uuid == null || uuid.isEmpty) {
        throw const ServerFailure(message: 'Gym not found.');
      }
      return GymLookup(uuid: uuid, name: name ?? 'your gym');
    } on DioException catch (e) {
      throw _mapDioError(e);
    }
  }

  Failure _mapDioError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.connectionError:
        return const NetworkFailure();
      case DioExceptionType.badResponse:
        final statusCode = e.response?.statusCode;
        final data = e.response?.data;
        final detail = data is Map ? data['detail'] : null;
        final message = detail?.toString() ?? 'Gym not found.';
        return ServerFailure(message: message, statusCode: statusCode);
      case DioExceptionType.cancel:
      case DioExceptionType.badCertificate:
      case DioExceptionType.transformTimeout:
      case DioExceptionType.unknown:
        return UnknownFailure(message: e.message ?? 'Unknown error');
    }
  }
}
