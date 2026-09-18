import '../../profile/data/models/customer_profile.dart';

/// Gym access status derived from the customer's membership end date.
enum AccessStatus {
  /// Membership end date is further away than the expiry-warning threshold.
  active,

  /// Membership ends today or within the expiry-warning threshold.
  expiringSoon,

  /// Membership end date has passed.
  expired,

  /// No membership / no end date available — nothing to report.
  unknown,
}

/// Result of an access-status evaluation: a ready-to-show notification plus
/// the structured data behind it.
class AccessStatusInfo {
  final AccessStatus status;
  final String title;
  final String message;
  final int? daysRemaining;
  final DateTime? endDate;

  const AccessStatusInfo({
    required this.status,
    required this.title,
    required this.message,
    this.daysRemaining,
    this.endDate,
  });

  /// Whether this status warrants notifying the customer.
  bool get shouldNotify =>
      status == AccessStatus.expiringSoon || status == AccessStatus.expired;
}

/// Computes device-access status notifications from membership end dates.
///
/// Pure, deterministic logic (pass [now] to control "today" in tests) so it
/// can drive local notifications, dashboard banners, or any other surface
/// without a plugin dependency.
class AccessStatusService {
  AccessStatusService._();

  /// Memberships ending within this many days trigger an expiry warning.
  static const int expiringSoonThresholdDays = 7;

  /// Evaluates access status from a single membership end date.
  static AccessStatusInfo evaluate(DateTime? endDate, {DateTime? now}) {
    if (endDate == null) {
      return const AccessStatusInfo(
        status: AccessStatus.unknown,
        title: 'Gym Access',
        message: 'No membership end date found',
      );
    }

    final today = _dateOnly(now ?? DateTime.now());
    final end = _dateOnly(endDate);
    final daysRemaining = end.difference(today).inDays;

    if (daysRemaining < 0) {
      return AccessStatusInfo(
        status: AccessStatus.expired,
        title: 'Access expired',
        message: 'Your gym access has expired',
        daysRemaining: daysRemaining,
        endDate: endDate,
      );
    }

    if (daysRemaining == 0) {
      return AccessStatusInfo(
        status: AccessStatus.expiringSoon,
        title: 'Access expiring soon',
        message: 'Your access expires today',
        daysRemaining: daysRemaining,
        endDate: endDate,
      );
    }

    if (daysRemaining == 1) {
      return AccessStatusInfo(
        status: AccessStatus.expiringSoon,
        title: 'Access expiring soon',
        message: 'Your access expires tomorrow',
        daysRemaining: daysRemaining,
        endDate: endDate,
      );
    }

    if (daysRemaining <= expiringSoonThresholdDays) {
      return AccessStatusInfo(
        status: AccessStatus.expiringSoon,
        title: 'Access expiring soon',
        message: 'Your access expires in $daysRemaining days',
        daysRemaining: daysRemaining,
        endDate: endDate,
      );
    }

    return AccessStatusInfo(
      status: AccessStatus.active,
      title: 'Gym access active',
      message: 'Your gym access is active',
      daysRemaining: daysRemaining,
      endDate: endDate,
    );
  }

  /// Evaluates access status across the customer's memberships.
  ///
  /// The membership with the latest end date defines the access window:
  /// if the longest one has expired, access has expired. Memberships
  /// without an end date are ignored.
  static AccessStatusInfo evaluateMemberships(
    List<Membership> memberships, {
    DateTime? now,
  }) {
    final endDates = memberships
        .map((m) => m.endDate)
        .whereType<DateTime>()
        .toList();
    if (endDates.isEmpty) {
      return evaluate(null, now: now);
    }

    final latest = endDates.reduce((a, b) => a.isAfter(b) ? a : b);
    return evaluate(latest, now: now);
  }

  /// Strips the time component so day counting is calendar-based.
  static DateTime _dateOnly(DateTime date) => DateTime(date.year, date.month, date.day);
}
