import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_card.dart';
import '../../data/models/diet_plan.dart';
import '../../data/models/meal.dart';

/// Shows the details of a meal day with its meals and food items.
class MealDetailScreen extends StatelessWidget {
  final DietPlan plan;
  final DietDay day;

  const MealDetailScreen({
    super.key,
    required this.plan,
    required this.day,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(day.name)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Day summary
          AppCard(
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _SummaryItem(label: 'Calories', value: '${day.totalCalories.round()}'),
                _SummaryItem(label: 'Protein', value: '${day.totalProtein.round()}g'),
                _SummaryItem(label: 'Meals', value: '${day.meals.length}'),
              ],
            ),
          ),
          const SizedBox(height: 16),
          for (final meal in day.meals) _MealCard(meal: meal),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: () => context.push(
              '/diet/log',
              extra: {'plan': plan, 'day': day},
            ),
            icon: const Icon(Icons.check_circle_outline),
            label: const Text('Log Meals'),
          ),
        ],
      ),
    );
  }
}

class _SummaryItem extends StatelessWidget {
  final String label;
  final String value;

  const _SummaryItem({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: AppTheme.primary),
        ),
        const SizedBox(height: 4),
        Text(label, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
      ],
    );
  }
}

class _MealCard extends StatelessWidget {
  final Meal meal;

  const _MealCard({required this.meal});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      margin: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: AppTheme.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.restaurant, color: AppTheme.primary),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      meal.name,
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                    ),
                    if (meal.mealType != null)
                      Text(
                        meal.mealType!,
                        style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                      ),
                  ],
                ),
              ),
              Text(
                '${meal.totalCalories.round()} kcal',
                style: const TextStyle(fontWeight: FontWeight.w600, color: AppTheme.primary),
              ),
            ],
          ),
          if (meal.foodItems.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Divider(height: 1),
            const SizedBox(height: 8),
            for (final food in meal.foodItems)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(food.name, style: const TextStyle(fontSize: 14)),
                    ),
                    Text(
                      '${food.calories?.round() ?? 0} kcal',
                      style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                    ),
                  ],
                ),
              ),
          ],
        ],
      ),
    );
  }
}
