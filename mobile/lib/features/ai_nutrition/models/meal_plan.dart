import 'meal_plan_item.dart';

/// A day of a meal plan with its items.
class MealPlanDay {
  final int? id;
  final int dayNumber;
  final List<MealPlanItem> items;

  const MealPlanDay({
    this.id,
    required this.dayNumber,
    this.items = const [],
  });

  factory MealPlanDay.fromJson(Map<String, dynamic> json) {
    return MealPlanDay(
      id: json['id'] as int?,
      dayNumber: json['day_number'] as int? ?? json['day'] as int? ?? 1,
      items: (json['items'] as List<dynamic>?)
              ?.map((e) => MealPlanItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        'day_number': dayNumber,
        'items': items.map((e) => e.toJson()).toList(),
      };

  /// Total calories for the day.
  double get totalCalories =>
      items.fold(0, (sum, i) => sum + (i.calories ?? 0));

  /// Total protein for the day.
  double get totalProtein =>
      items.fold(0, (sum, i) => sum + (i.protein ?? 0));

  /// Total carbs for the day.
  double get totalCarbs =>
      items.fold(0, (sum, i) => sum + (i.carbs ?? 0));

  /// Total fat for the day.
  double get totalFat =>
      items.fold(0, (sum, i) => sum + (i.fat ?? 0));
}

/// A full AI-generated meal plan.
class MealPlan {
  final int? id;
  final String name;
  final String? description;
  final double? targetCalories;
  final int? durationDays;
  final List<MealPlanDay> days;

  const MealPlan({
    this.id,
    required this.name,
    this.description,
    this.targetCalories,
    this.durationDays,
    this.days = const [],
  });

  factory MealPlan.fromJson(Map<String, dynamic> json) {
    return MealPlan(
      id: json['id'] as int?,
      name: json['name'] as String? ?? 'Meal Plan',
      description: json['description'] as String?,
      targetCalories: (json['target_calories'] as num?)?.toDouble(),
      durationDays: json['duration_days'] as int?,
      days: (json['days'] as List<dynamic>?)
              ?.map((e) => MealPlanDay.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        'name': name,
        if (description != null) 'description': description,
        if (targetCalories != null) 'target_calories': targetCalories,
        if (durationDays != null) 'duration_days': durationDays,
        'days': days.map((e) => e.toJson()).toList(),
      };

  /// Daily average macros across the plan.
  double get averageCalories => days.isEmpty
      ? 0
      : days.fold<double>(0, (s, d) => s + d.totalCalories) / days.length;
}
