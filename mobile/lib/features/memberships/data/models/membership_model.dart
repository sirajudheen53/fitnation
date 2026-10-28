/// One membership of the logged-in customer.
///
/// Mirrors the payload of GET /api/v1/memberships/memberships/ (issue #95),
/// which is self-scoped server-side when the caller is a customer.
class MembershipModel {
  final int id;
  final int? plan;
  final String planName;
  final num price;
  final DateTime startDate;
  final DateTime? endDate;

  /// active | expired | cancelled.
  final String status;
  final bool autoRenew;

  const MembershipModel({
    required this.id,
    this.plan,
    required this.planName,
    required this.price,
    required this.startDate,
    this.endDate,
    required this.status,
    this.autoRenew = false,
  });

  factory MembershipModel.fromJson(Map<String, dynamic> json) {
    return MembershipModel(
      id: json['id'] as int,
      plan: json['plan'] as int?,
      planName: json['plan_name'] as String? ?? 'Membership',
      price: (json['price'] as num?) ?? 0,
      startDate: DateTime.parse(json['start_date'] as String),
      endDate: json['end_date'] == null
          ? null
          : DateTime.parse(json['end_date'] as String),
      status: json['status'] as String,
      autoRenew: (json['auto_renew'] as bool?) ?? false,
    );
  }

  bool get isActive => status == 'active';

  /// The membership to show on the home card: the active one if any,
  /// otherwise the most recent record returned by the API.
  static MembershipModel? pickCurrent(List<MembershipModel> memberships) {
    if (memberships.isEmpty) return null;
    return memberships.firstWhere(
      (m) => m.isActive,
      orElse: () => memberships.first,
    );
  }

  @override
  String toString() =>
      'MembershipModel(id: $id, plan: $planName, status: $status)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is MembershipModel && other.id == id;

  @override
  int get hashCode => id.hashCode;
}
