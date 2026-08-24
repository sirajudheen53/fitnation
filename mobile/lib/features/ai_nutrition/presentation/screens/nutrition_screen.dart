import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/async_view.dart';
import '../../models/meal_plan.dart';
import '../providers/ai_nutrition_provider.dart';

/// AI Nutrition dashboard: meal plan summary, macro tracking, and actions.
class NutritionScreen extends ConsumerStatefulWidget {
  const NutritionScreen({super.key});

  @override
  ConsumerState<NutritionScreen> createState() => _NutritionScreenState();
}

class _NutritionScreenState extends ConsumerState<NutritionScreen> {
  bool _showingShoppingList = false;

  void _toggleShoppingList() {
    setState(() => _showingShoppingList = !_showingShoppingList);
  }

  @override
  Widget build(BuildContext context) {
    final plansAsync = ref.watch(mealPlansProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('AI Nutrition')),
      body: AsyncView<List<MealPlan>>(
        value: plansAsync,
        onRetry: () => ref.invalidate(mealPlansProvider),
        builder: (plans) {
          final activePlan = plans.isNotEmpty ? plans.first : null;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (activePlan != null)
                _MealPlanSummary(
                  plan: activePlan,
                  onTap: () => context.push(
                    '/nutrition/detail',
                    extra: {'plan': activePlan},
                  ),
                )
              else
                const EmptyState(
                  icon: Icons.restaurant_menu,
                  title: 'No meal plan yet',
                  subtitle: 'Generate an AI meal plan to get started.',
                ),
              const SizedBox(height: 20),

              const SectionHeader(title: 'Daily Macros'),
              const SizedBox(height: 12),
              _MacroTracking(plan: activePlan),
              const SizedBox(height: 20),

              const SectionHeader(title: 'Meal Plan'),
              const SizedBox(height: 12),
              _MealPlanActions(
                plan: activePlan,
                showingShoppingList: _showingShoppingList,
                onToggleShoppingList: _toggleShoppingList,
              ),
              if (_showingShoppingList) ...[
                const SizedBox(height: 12),
                _ShoppingList(planId: activePlan?.id),
              ],
            ],
          );
        },
      ),
    );
  }
}

class _MealPlanSummary extends StatelessWidget {
  final MealPlan plan;
  final VoidCallback onTap;
  const _MealPlanSummary({required this.plan, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.auto_awesome, color: AppTheme.primary),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  plan.name,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                ),
              ),
              const Icon(Icons.chevron_right, color: AppTheme.textSecondary),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            plan.description ?? 'Your AI-generated meal plan',
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
          ),
          if (plan.targetCalories != null) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                _MiniStat(
                  icon: Icons.local_fire_department,
                  label: '${plan.targetCalories!.round()} kcal/day',
                ),
                const SizedBox(width: 16),
                _MiniStat(
                  icon: Icons.calendar_today,
                  label: '${plan.durationDays ?? plan.days.length} days',
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  final IconData icon;
  final String label;
  const _MiniStat({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 16, color: AppTheme.primary),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 13)),
      ],
    );
  }
}

class _MacroTracking extends StatelessWidget {
  final MealPlan? plan;
  const _MacroTracking({this.plan});

  @override
  Widget build(BuildContext context) {
    final target = plan?.targetCalories ?? 2000;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Calories: ${consumedCalories.round()}/${target.round()}',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              Text(
                '${((consumedCalories / target) * 100).clamp(0, 100).round()}%',
                style: const TextStyle(color: AppTheme.primary, fontWeight: FontWeight.w700),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: LinearProgressIndicator(
              value: (consumedCalories / target).clamp(0.0, 1.0),
              minHeight: 10,
              backgroundColor: AppTheme.divider,
              valueColor: const AlwaysStoppedAnimation(AppTheme.primary),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              _MacroBar(
                label: 'Protein',
                value: proteinConsumed,
                target: plan?.averageCalories != 0 ? (target * 0.30) : 150,
                color: const Color(0xFFE53935),
              ),
              _MacroBar(
                label: 'Carbs',
                value: carbsConsumed,
                target: plan?.averageCalories != 0 ? (target * 0.50) : 250,
                color: const Color(0xFFFB8C00),
              ),
              _MacroBar(
                label: 'Fat',
                value: fatConsumed,
                target: plan?.averageCalories != 0 ? (target * 0.20) : 70,
                color: const Color(0xFF43A047),
              ),
            ],
          ),
          const SizedBox(height: 12),
          const Text(
            'Sample intake based on your plan. Log meals for live tracking.',
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 12),
          ),
        ],
      ),
    );
  }
}

// Placeholder values until live macro logging is wired in.
double get consumedCalories => 1280;
double get proteinConsumed => 62;
double get carbsConsumed => 168;
double get fatConsumed => 34;

class _MacroBar extends StatelessWidget {
  final String label;
  final double value;
  final double target;
  final Color color;
  const _MacroBar({
    required this.label,
    required this.value,
    required this.target,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final pct = ((value / target) * 100).clamp(0, 100).round();
    return Expanded(
      child: Column(
        children: [
          Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          SizedBox(
            height: 60,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Text('$pct%', style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                const SizedBox(height: 4),
                Container(
                  width: 28,
                  height: 34,
                  alignment: Alignment.bottomCenter,
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Container(
                    height: 34 * (pct / 100.0),
                    decoration: BoxDecoration(
                      color: color,
                      borderRadius: BorderRadius.circular(6),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 4),
          Text('${value.round()}g', style: const TextStyle(fontSize: 12)),
        ],
      ),
    );
  }
}

class _MealPlanActions extends StatelessWidget {
  final MealPlan? plan;
  final bool showingShoppingList;
  final VoidCallback onToggleShoppingList;
  const _MealPlanActions({
    required this.plan,
    required this.showingShoppingList,
    required this.onToggleShoppingList,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        ElevatedButton.icon(
          onPressed: plan != null
              ? () => context.push('/nutrition/detail', extra: {'plan': plan})
              : () => context.push('/nutrition/generate'),
          icon: const Icon(Icons.edit_calendar),
          label: Text(plan != null ? 'View Meal Plan' : 'Generate New Plan'),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: onToggleShoppingList,
          icon: Icon(
            showingShoppingList ? Icons.expand_less : Icons.shopping_cart,
          ),
          label: Text(showingShoppingList ? 'Hide Shopping List' : 'Shopping List'),
        ),
      ],
    );
  }
}

class _ShoppingList extends ConsumerWidget {
  final int? planId;
  const _ShoppingList({this.planId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final itemsAsync = ref.watch(shoppingListProvider(planId));

    return AppCard(
      child: itemsAsync.when(
        data: (items) {
          if (items.isEmpty) {
            return const Text('No shopping list generated yet.',
                style: TextStyle(color: AppTheme.textSecondary));
          }
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Shopping List',
                  style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
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
                      Expanded(
                        child: Text(
                          item.name,
                          style: TextStyle(
                            decoration: item.isChecked
                                ? TextDecoration.lineThrough
                                : null,
                          ),
                        ),
                      ),
                      if (item.quantity != null)
                        Text(
                          '${item.quantity} ${item.unit ?? ''}',
                          style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
                        ),
                    ],
                  ),
                ),
            ],
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Text(
          'Could not load shopping list.',
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
      ),
    );
  }
}
