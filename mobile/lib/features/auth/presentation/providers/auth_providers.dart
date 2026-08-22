import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data_sources/api_client.dart';
import '../../data/data_sources/auth_local_data_source.dart';
import '../../data/data_sources/auth_remote_data_source.dart';
import '../../domain/repositories/auth_repository.dart';

/// Provides the AuthLocalDataSource singleton.
/// Initialized in main.dart before app starts, and overridden in ProviderScope.
final authLocalDataSourceProvider = Provider<AuthLocalDataSource>((ref) {
  return AuthLocalDataSource();
});

/// Provides the AuthRemoteDataSource.
final authRemoteDataSourceProvider = Provider<AuthRemoteDataSource>((ref) {
  final dio = ApiClient.getInstance();
  return AuthRemoteDataSource(dio);
});

/// Provides the AuthRepository.
final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final remote = ref.read(authRemoteDataSourceProvider);
  final local = ref.read(authLocalDataSourceProvider);
  return AuthRepository(remote, local);
});