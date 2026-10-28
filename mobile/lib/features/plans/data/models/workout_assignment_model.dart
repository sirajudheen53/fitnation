/// An active workout-plan assignment for the logged-in customer.
///
/// Mirrors the payload of GET /api/v1/workouts/workout-assignments/active/
/// (issue #90), which returns the customer's own active assignments when the
/// caller is a customer.
class WorkoutAssignmentModel {
  final int id;
  final int customer;
  final int workoutPlan;
  final String workoutPlanName;
  final String customerName;
  final bool customerIsDeleted;
  final DateTime startDate;
  final DateTime? endDate;
  final bool isActive;
  final int? assignedBy;
  final String? notes;
  final DateTime createdAt;
  final DateTime updatedAt;

  const WorkoutAssignmentModel({
    required this.id,
    required this.customer,
    required this.workoutPlan,
    required this.workoutPlanName,
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

  factory WorkoutAssignmentModel.fromJson(Map<String, dynamic> json) {
    return WorkoutAssignmentModel(
      id: json['id'] as int,
      customer: json['customer'] as int,
      workoutPlan: json['workout_plan'] as int,
      workoutPlanName: json['workout_plan_name'] as String,
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
        'workout_plan': workoutPlan,
        'workout_plan_name': workoutPlanName,
        'customer_name': customerName,
        'customer_is_deleted': customerIsDeleted,
        'start_date': startDate.toIso8601String().substring(0, 10),
        'end_date':
            endDate?.toIso8601String().substring(0, 10),
        'is_active': isActive,
        'assigned_by': assignedBy,
        'notes': notes,
        'created_at': createdAt.toIso8601String(),
        'updated_at': updatedAt.toIso8601String(),
      };

  @override
  String toString() =>
      'WorkoutAssignmentModel(id: $id, plan: $workoutPlanName, active: $isActive)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is WorkoutAssignmentModel && other.id == id;

  @override
  int get hashCode => id.hashCode;
}
