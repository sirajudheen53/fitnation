import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_card.dart';
import '../../models/meal_plan.dart';
import '../../models/meal_plan_item.dart';
import '../providers/ai_nutrition_provider.dart';

/// Meal plan detail: 7-day grid with meals and macros per day.
class MealPlanDetailScreen extends ConsumerWidget {
  const MealPlanDetailScreen({super.key, required this.plan});

  final MealPlan plan;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(title: Text(plan.name)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _PlanHeader(plan: plan),
          const SizedBox(height: 20),

          const SectionHeader(title: '7-Day Plan'),
          const SizedBox(height: 12),
          if (plan.days.isEmpty)
            const EmptyState(
              icon: Icons.event_note,
              title: 'No days in this plan',
            )
          else
            for (final day in plan.days) _DayCard(day: day),
          const SizedBox(height: 20),

          _GenerateShoppingListButton(planId: plan.id),
        ],
      ),
    );
  }
}

class _PlanHeader extends StatelessWidget {
  final MealPlan plan;
  const _PlanHeader({required this.plan});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppTheme.primary, AppTheme.primaryLight],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.auto_awesome, color: Colors.white),
              SizedBox(width: 8),
              Text(
                'AI Generated',
                style: TextStyle(color: Colors.white70, fontSize: 13),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            plan.description ?? plan.name,
            style: const TextStyle(color: Colors.white, fontSize: 15),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              if (plan.targetCalories != null)
                _HeaderStat(
                  icon: Icons.local_fire_department,
                  label: '${plan.targetCalories!.round()} kcal',
                ),
              const SizedBox(width: 16),
              _HeaderStat(
                icon: Icons.calendar_today,
                label: '${plan.durationDays ?? plan.days.length} days',
              ),
              const SizedBox(width: 16),
              _HeaderStat(
                icon: Icons.restaurant,
                label: '${plan.days.length} days',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _HeaderStat extends StatelessWidget {
  final IconData icon;
  final String label;
  const _HeaderStat({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, color: Colors.white, size: 16),
        const SizedBox(width: 4),
        Text(
          label,
          style: const TextStyle(color: Colors.white, fontSize: 13),
        ),
      ],
    );
  }
}

class _DayCard extends StatelessWidget {
  final MealPlanDay day;
  const _DayCard({required this.day});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      margin: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(
                      color: AppTheme.primary.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Center(
                      child: Text(
                        '${day.dayNumber}',
                        style: const TextStyle(
                          color: AppTheme.primary,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'Day ${day.dayNumber}',
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                  ),
                ],
              ),
              Text(
                '${day.totalCalories.round()} kcal',
                style: const TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 12,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _MacroRow(
            protein: day.totalProtein,
            carbs: day.totalCarbs,
            fat: day.totalFat,
          ),
          const SizedBox(height: 12),
          for (final item in day.items) _MealTile(item: item),
        ],
      ),
    );
  }
}

class _MacroRow extends StatelessWidget {
  final double protein;
  final double carbs;
  final double fat;
  const _MacroRow({
    required this.protein,
    required this.carbs,
    required this.fat,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        _MacroChip(label: 'Protein', value: protein, color: const Color(0xFFE53935)),
        const SizedBox(width: 8),
        _MacroChip(label: 'Carbs', value: carbs, color: const Color(0xFFFB8C00)),
        const SizedBox(width: 8),
        _MacroChip(label: 'Fat', value: fat, color: const Color(0xFF43A047)),
      ],
    );
  }
}

class _MacroChip extends StatelessWidget {
  final String label;
  final double value;
  final Color color;
  const _MacroChip({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        '$label ${value.round()}g',
        style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600),
      ),
    );
  }
}

class _MealTile extends StatelessWidget {
  final MealPlanItem item;
  const _MealTile({required this.item});

  IconData get _typeIcon {
    switch (item.mealType) {
      case 'breakfast':
        return Icons.wb_sunny_outlined;
      case 'lunch':
        return Icons.lunch_dining;
      case 'snack':
        return Icons.cookie_outlined;
      case 'dinner':
        return Icons.nights_stay_outlined;
      default:
        return Icons.restaurant;
    }
  }

  String get _typeLabel => item.mealType[0].toUpperCase() + item.mealType.substring(1);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(_typeIcon, size: 20, color: AppTheme.primary),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _typeLabel,
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppTheme.textSecondary,
                  ),
                ),
                Text(
                  item.name,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
          if (item.calories != null)
            Text(
              '${item.calories!.round()} kcal',
              style: const TextStyle(fontSize: 13),
            ),
        ],
      ),
    );
  }
}

class _GenerateShoppingListButton extends ConsumerWidget {
  final int? planId;
  const _GenerateShoppingListButton({this.planId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final listAsync = ref.watch(shoppingListProvider(planId));

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Shopping List',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 12),
          listAsync.when(
            data: (items) {
              if (items.isEmpty) {
                return const Text(
                  'Generate a shopping list for this meal plan.',
                  style: TextStyle(color: AppTheme.textSecondary),
                );
              }
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final item in items)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Row(
                        children: [
                          Icon(
                            item.isChecked
                                ? Icons.check_box
                                : Icons.check_box_outline_blank,
                            color: AppTheme.primary,
                            size: 20,
                          ),
                          const SizedBox(width: 8),
                          Expanded(child: Text(item.name)),
                          if (item.quantity != null)
                            Text(
                              '${item.quantity} ${item.unit ?? ''}',
                              style: const TextStyle(
                                color: AppTheme.textSecondary,
                                fontSize: 12,
                              ),
                            ),
                        ],
                      ),
                    ),
                ],
              );
            },
            loading: () => const Center(
              child: Padding(
                padding: EdgeInsets.all(8),
                child: CircularProgressIndicator(),
              ),
            ),
            error: (e, _) => Text(
              'Could not load shopping list.',
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
          const SizedBox(height: 12),
          ElevatedButton.icon(
            onPressed: () => ref.invalidate(shoppingListProvider(planId)),
            icon: const Icon(Icons.shopping_cart),
            label: const Text('Generate Shopping List'),
          ),
        ],
      ),
    );
  }
}
