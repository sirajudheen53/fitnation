/// An active diet (meal) plan assignment for the logged-in customer.
///
/// Mirrors the payload of GET /api/v1/diet-assignments/active/ (issue #90),
/// which returns the customer's own active assignments when the caller is a
/// customer.
class DietAssignmentModel {
  final int id;
  final int customer;
  final int dietPlan;
  final String dietPlanName;
  final String customerName;
  final bool customerIsDeleted;
  final DateTime startDate;
  final DateTime? endDate;
  final bool isActive;
  final int? assignedBy;
  final String? notes;
  final DateTime createdAt;
  final DateTime updatedAt;

  const DietAssignmentModel({
    required this.id,
    required this.customer,
    required this.dietPlan,
    required this.dietPlanName,
    required this.customerName,
    this.customerIsDeleted = false,
    required this.startDate,
    this.endDate,
    this.isActive = true,
    this.assignedBy,
    this.notes,
    required this.createdAt,
    required this.updatedAt,
  });

  factory DietAssignmentModel.fromJson(Map<String, dynamic> json) {
    return DietAssignmentModel(
      id: json['id'] as int,
      customer: json['customer'] as int,
      dietPlan: json['diet_plan'] as int,
      dietPlanName: json['diet_plan_name'] as String,
      customerName: json['customer_name'] as String,
      customerIsDeleted: (json['customer_is_deleted'] as bool?) ?? false,
      startDate: DateTime.parse(json['start_date'] as String),
      endDate: json['end_date'] == null
          ? null
          : DateTime.parse(json['end_date'] as String),
      isActive: (json['is_active'] as bool?) ?? false,
      assignedBy: json['assigned_by'] as int?,
      notes: json['notes'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'customer': customer,
        'diet_plan': dietPlan,
        'diet_plan_name': dietPlanName,
        'customer_name': customerName,
        'customer_is_deleted': customerIsDeleted,
        'start_date': startDate.toIso8601String().substring(0, 10),
        'end_date': endDate?.toIso8601String().substring(0, 10),
        'is_active': isActive,
        'assigned_by': assignedBy,
        'notes': notes,
        'created_at': createdAt.toIso8601String(),
        'updated_at': updatedAt.toIso8601String(),
      };

  @override
  String toString() =>
      'DietAssignmentModel(id: $id, plan: $dietPlanName, active: $isActive)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is DietAssignmentModel && other.id == id;

  @override
  int get hashCode => id.hashCode;
}
