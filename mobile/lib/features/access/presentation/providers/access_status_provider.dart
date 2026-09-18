import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../profile/presentation/providers/profile_provider.dart';
import '../../services/access_status_service.dart';

/// Current gym access status for the logged-in customer, derived from
/// their memberships. Null while memberships are loading or unavailable.
///
/// Consumers can surface [AccessStatusInfo.shouldNotify] results as a
/// local notification or in-app banner (e.g. 'Your access expires in 3 days').
final accessStatusProvider = Provider<AccessStatusInfo?>((ref) {
  final membershipsAsync = ref.watch(membershipsProvider);

  return membershipsAsync.maybeWhen(
    data: (memberships) =>
        AccessStatusService.evaluateMemberships(memberships),
    orElse: () => null,
  );
});
