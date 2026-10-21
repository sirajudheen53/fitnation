/// The member's app-access entitlement (FBOS-011 §2.3, ADR-003).
///
/// Parsed from the `entitlement` object the backend attaches to the OTP-verify
/// and `/auth/me/` responses and returned by `GET /users/auth/entitlement/`:
///
/// ```json
/// {"status": "grace", "read_only": true, "plan_name": "Monthly Unlimited",
///  "end_date": "2026-10-14", "grace_end_date": "2026-10-21",
///  "gym": {"uuid": "3f7c…", "name": "Hash Fit"}}
/// ```
library;

/// Entitlement status values served by the backend
/// (`apps/memberships/selectors.py::EntitlementStatus`).
enum AppEntitlementStatus {
  /// Full access.
  active,

  /// Membership expired — read-only grace window (writes blocked).
  grace,

  /// Grace over — the app gates the member out.
  expired,

  /// No entitlement (never a member, plan without app access, flag off).
  none;

  static AppEntitlementStatus fromString(String? value) =>
      AppEntitlementStatus.values.firstWhere(
        (s) => s.name == value,
        orElse: () => AppEntitlementStatus.none,
      );
}

/// Immutable snapshot of the member's app-access state.
class Entitlement {
  const Entitlement({
    required this.status,
    this.readOnly = false,
    this.planName,
    this.endDate,
    this.graceEndDate,
    this.gymUuid,
    this.gymName,
  });

  /// Parses the backend payload; missing/unknown fields degrade safely.
  factory Entitlement.fromJson(Map<String, dynamic> json) {
    final gym = json['gym'];
    DateTime? parseDate(String? raw) {
      if (raw == null || raw.isEmpty) return null;
      return DateTime.tryParse(raw);
    }

    return Entitlement(
      status: AppEntitlementStatus.fromString(json['status'] as String?),
      readOnly: (json['read_only'] as bool?) ?? false,
      planName: json['plan_name'] as String?,
      endDate: parseDate(json['end_date'] as String?),
      graceEndDate: parseDate(json['grace_end_date'] as String?),
      gymUuid: gym is Map<String, dynamic> ? gym['uuid'] as String? : null,
      gymName: gym is Map<String, dynamic> ? gym['name'] as String? : null,
    );
  }

  /// The entitlement state.
  final AppEntitlementStatus status;

  /// True in the read-only grace window (writes must be disabled).
  final bool readOnly;

  /// Plan display name for gate/banner copy.
  final String? planName;

  /// Membership end date (the "expired on" copy date).
  final DateTime? endDate;

  /// Last day of the grace window (banner copy).
  final DateTime? graceEndDate;

  /// Anchored gym — shown on the gate screen.
  final String? gymUuid;

  /// Anchored gym display name — shown on the gate screen.
  final String? gymName;

  /// The member may use the app right now (grace counts, read-only).
  bool get isEntitled =>
      status == AppEntitlementStatus.active || status == AppEntitlementStatus.grace;

  /// The router must send the member to `/gate`.
  bool get requiresGate => !isEntitled;

  /// The full experience minus write actions.
  bool get isReadOnlyGrace =>
      status == AppEntitlementStatus.grace && readOnly;

  Entitlement copyWith({
    AppEntitlementStatus? status,
    bool? readOnly,
    String? planName,
    DateTime? endDate,
    DateTime? graceEndDate,
    String? gymUuid,
    String? gymName,
  }) {
    return Entitlement(
      status: status ?? this.status,
      readOnly: readOnly ?? this.readOnly,
      planName: planName ?? this.planName,
      endDate: endDate ?? this.endDate,
      graceEndDate: graceEndDate ?? this.graceEndDate,
      gymUuid: gymUuid ?? this.gymUuid,
      gymName: gymName ?? this.gymName,
    );
  }

  Map<String, dynamic> toJson() => {
        'status': status.name,
        'read_only': readOnly,
        'plan_name': planName,
        'end_date': endDate?.toIso8601String(),
        'grace_end_date': graceEndDate?.toIso8601String(),
        'gym': gymUuid == null && gymName == null
            ? null
            : {'uuid': gymUuid, 'name': gymName},
      }..removeWhere((_, v) => v == null);

  @override
  String toString() => 'Entitlement(${status.name}, readOnly: $readOnly, '
      'plan: $planName, gym: $gymName)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Entitlement &&
          other.status == status &&
          other.readOnly == readOnly &&
          other.planName == planName &&
          other.endDate == endDate &&
          other.graceEndDate == graceEndDate &&
          other.gymUuid == gymUuid &&
          other.gymName == gymName;

  @override
  int get hashCode => Object.hash(status, readOnly, planName, endDate,
      graceEndDate, gymUuid, gymName);
}
