import 'meal.dart';

/// A diet day within a plan, containing meals.
class DietDay {
  final int? id;
  final String name;
  final int? dayNumber;
  final List<Meal> meals;

  const DietDay({
    this.id,
    required this.name,
    this.dayNumber,
    this.meals = const [],
  });

  factory DietDay.fromJson(Map<String, dynamic> json) {
    return DietDay(
      id: json['id'] as int?,
      name: json['name'] as String? ?? 'Day',
      dayNumber: json['day_number'] as int?,
      meals: (json['meals'] as List<dynamic>?)
              ?.map((e) => Meal.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        'name': name,
        if (dayNumber != null) 'day_number': dayNumber,
        'meals': meals.map((e) => e.toJson()).toList(),
      };

  /// Total calories across all meals.
  double get totalCalories =>
      meals.fold(0, (sum, m) => sum + m.totalCalories);

  /// Total protein across all meals.
  double get totalProtein =>
      meals.fold(0, (sum, m) => sum + m.totalProtein);
}

/// A diet plan with its days.
class DietPlan {
  final int id;
  final String name;
  final String? description;
  final int? durationWeeks;
  final int? mealsPerDay;
  final double? targetCalories;
  final List<DietDay> days;

  const DietPlan({
    required this.id,
    required this.name,
    this.description,
    this.durationWeeks,
    this.mealsPerDay,
    this.targetCalories,
    this.days = const [],
  });

  factory DietPlan.fromJson(Map<String, dynamic> json) {
    return DietPlan(
      id: json['id'] as int,
      name: json['name'] as String? ?? 'Diet Plan',
      description: json['description'] as String?,
      durationWeeks: json['duration_weeks'] as int?,
      mealsPerDay: json['meals_per_day'] as int?,
      targetCalories: (json['target_calories'] as num?)?.toDouble(),
      days: (json['days'] as List<dynamic>?)
              ?.map((e) => DietDay.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        if (description != null) 'description': description,
        if (durationWeeks != null) 'duration_weeks': durationWeeks,
        if (mealsPerDay != null) 'meals_per_day': mealsPerDay,
        if (targetCalories != null) 'target_calories': targetCalories,
        'days': days.map((e) => e.toJson()).toList(),
      };
}

/// A diet assignment linking a customer to a plan.
class DietAssignment {
  final int id;
  final int customerId;
  final int planId;
  final String? planName;
  final bool isActive;
  final DateTime? assignedAt;
  final DateTime? startDate;
  final DateTime? endDate;

  const DietAssignment({
    required this.id,
    required this.customerId,
    required this.planId,
    this.planName,
    this.isActive = true,
    this.assignedAt,
    this.startDate,
    this.endDate,
  });

  factory DietAssignment.fromJson(Map<String, dynamic> json) {
    return DietAssignment(
      id: json['id'] as int,
      customerId: json['customer'] as int? ?? json['customer_id'] as int? ?? 0,
      planId: json['plan'] as int? ?? json['plan_id'] as int? ?? 0,
      planName: json['plan_name'] as String?,
      isActive: (json['is_active'] as bool?) ?? true,
      assignedAt: json['assigned_at'] != null
          ? DateTime.tryParse(json['assigned_at'].toString())
          : null,
      startDate: json['start_date'] != null
          ? DateTime.tryParse(json['start_date'].toString())
          : null,
      endDate: json['end_date'] != null
          ? DateTime.tryParse(json['end_date'].toString())
          : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'customer': customerId,
        'plan': planId,
        if (planName != null) 'plan_name': planName,
        'is_active': isActive,
      };
}
