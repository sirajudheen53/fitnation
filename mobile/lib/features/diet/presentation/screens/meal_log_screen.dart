import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../data/models/diet_plan.dart';
import '../../data/models/meal.dart';
import '../providers/diet_provider.dart';

/// Screen for marking meals complete.
class MealLogScreen extends ConsumerStatefulWidget {
  final DietPlan plan;
  final DietDay day;

  const MealLogScreen({
    super.key,
    required this.plan,
    required this.day,
  });

  @override
  ConsumerState<MealLogScreen> createState() => _MealLogScreenState();
}

class _MealLogScreenState extends ConsumerState<MealLogScreen> {
  final Set<int> _completedMealIds = {};

  Future<void> _markComplete(Meal meal) async {
    final success = await ref.read(mealLogProvider.notifier).markMealComplete(meal);
    if (success && mounted) {
      setState(() => _completedMealIds.add(meal.id ?? meal.name.hashCode));
    }
  }

  @override
  Widget build(BuildContext context) {
    final logState = ref.watch(mealLogProvider);

    return Scaffold(
      appBar: AppBar(title: Text('Log ${widget.day.name}')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'Mark meals as complete as you finish them.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: AppTheme.textSecondary,
                ),
          ),
          const SizedBox(height: 16),
          for (final meal in widget.day.meals) _buildMealTile(meal),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: logState.isLoading
                ? null
                : () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Meals logged successfully!')),
                    );
                    context.pop();
                  },
            child: logState.isLoading
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Text('Done'),
          ),
        ],
      ),
    );
  }

  Widget _buildMealTile(Meal meal) {
    final isComplete = _completedMealIds.contains(meal.id ?? meal.name.hashCode);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isComplete ? AppTheme.accent : AppTheme.divider,
          width: isComplete ? 1.5 : 1,
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  meal.name,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 4),
                Text(
                  '${meal.foodItems.length} items · ${meal.totalCalories.round()} kcal',
                  style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                ),
              ],
            ),
          ),
          Checkbox(
            value: isComplete,
            onChanged: (v) {
              if (v == true) _markComplete(meal);
            },
          ),
        ],
      ),
    );
  }
}
