/// A food item within a meal.
class FoodItem {
  final int? id;
  final String name;
  final double? calories;
  final double? protein;
  final double? carbs;
  final double? fat;
  final double? quantity;
  final String? unit;
  final String? servingSize;

  const FoodItem({
    this.id,
    required this.name,
    this.calories,
    this.protein,
    this.carbs,
    this.fat,
    this.quantity,
    this.unit,
    this.servingSize,
  });

  factory FoodItem.fromJson(Map<String, dynamic> json) {
    return FoodItem(
      id: json['id'] as int?,
      name: json['name'] as String? ?? 'Food',
      calories: (json['calories'] as num?)?.toDouble(),
      protein: (json['protein'] as num?)?.toDouble(),
      carbs: (json['carbs'] as num?)?.toDouble(),
      fat: (json['fat'] as num?)?.toDouble(),
      quantity: (json['quantity'] as num?)?.toDouble(),
      unit: json['unit'] as String?,
      servingSize: json['serving_size'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        'name': name,
        if (calories != null) 'calories': calories,
        if (protein != null) 'protein': protein,
        if (carbs != null) 'carbs': carbs,
        if (fat != null) 'fat': fat,
        if (quantity != null) 'quantity': quantity,
        if (unit != null) 'unit': unit,
        if (servingSize != null) 'serving_size': servingSize,
      };
}

/// A meal within a diet day, containing food items.
class Meal {
  final int? id;
  final String name;
  final String? mealType;
  final String? description;
  final List<FoodItem> foodItems;
  final bool isCompleted;

  const Meal({
    this.id,
    required this.name,
    this.mealType,
    this.description,
    this.foodItems = const [],
    this.isCompleted = false,
  });

  factory Meal.fromJson(Map<String, dynamic> json) {
    return Meal(
      id: json['id'] as int?,
      name: json['name'] as String? ?? 'Meal',
      mealType: json['meal_type'] as String?,
      description: json['description'] as String?,
      foodItems: (json['food_items'] as List<dynamic>?)
              ?.map((e) => FoodItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      isCompleted: (json['is_completed'] as bool?) ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        'name': name,
        if (mealType != null) 'meal_type': mealType,
        if (description != null) 'description': description,
        'food_items': foodItems.map((e) => e.toJson()).toList(),
        'is_completed': isCompleted,
      };

  /// Total calories across all food items.
  double get totalCalories =>
      foodItems.fold(0, (sum, f) => sum + (f.calories ?? 0));

  /// Total protein across all food items.
  double get totalProtein =>
      foodItems.fold(0, (sum, f) => sum + (f.protein ?? 0));

  Meal copyWith({bool? isCompleted}) {
    return Meal(
      id: id,
      name: name,
      mealType: mealType,
      description: description,
      foodItems: foodItems,
      isCompleted: isCompleted ?? this.isCompleted,
    );
  }
}
