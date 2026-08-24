/// A single meal item within a meal plan day.
class MealPlanItem {
  final int? id;
  final String name;
  final String mealType;
  final String? description;
  final double? calories;
  final double? protein;
  final double? carbs;
  final double? fat;

  const MealPlanItem({
    this.id,
    required this.name,
    required this.mealType,
    this.description,
    this.calories,
    this.protein,
    this.carbs,
    this.fat,
  });

  factory MealPlanItem.fromJson(Map<String, dynamic> json) {
    return MealPlanItem(
      id: json['id'] as int?,
      name: json['name'] as String? ?? 'Meal',
      mealType: json['meal_type'] as String? ?? 'meal',
      description: json['description'] as String?,
      calories: (json['calories'] as num?)?.toDouble(),
      protein: (json['protein'] as num?)?.toDouble(),
      carbs: (json['carbs'] as num?)?.toDouble(),
      fat: (json['fat'] as num?)?.toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        'name': name,
        'meal_type': mealType,
        if (description != null) 'description': description,
        if (calories != null) 'calories': calories,
        if (protein != null) 'protein': protein,
        if (carbs != null) 'carbs': carbs,
        if (fat != null) 'fat': fat,
      };
}
