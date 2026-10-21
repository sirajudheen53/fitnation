import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/data/data_sources/api_client.dart';
import '../../data/data_sources/tenant_lookup_remote_data_source.dart';

/// Provides the gym-code lookup data source.
final tenantLookupRemoteDataSourceProvider =
    Provider<TenantLookupRemoteDataSource>((ref) {
  return TenantLookupRemoteDataSource(ApiClient.getInstance());
});
