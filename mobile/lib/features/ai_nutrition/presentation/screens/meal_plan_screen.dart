import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_card.dart';
import '../../models/meal_plan.dart';
import '../../models/meal_plan_item.dart';
import '../providers/ai_nutrition_provider.dart';

/// AI meal plan generator: 7-day grid of meals and a preferences dialog.
///
/// Reached from `/nutrition/generate` when no plan exists yet. Lets the user
/// pick dietary preferences and generate a brand new AI meal plan.
class MealPlanScreen extends ConsumerStatefulWidget {
  const MealPlanScreen({super.key});

  @override
  ConsumerState<MealPlanScreen> createState() => _MealPlanScreenState();
}

class _MealPlanScreenState extends ConsumerState<MealPlanScreen> {
  String _goal = 'weight_loss';
  String _dietType = 'balanced';
  int _calories = 2000;
  int _mealsPerDay = 3;

  Future<void> _openPreferences() async {
    final result = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _PreferencesSheet(
        goal: _goal,
        dietType: _dietType,
        calories: _calories,
        mealsPerDay: _mealsPerDay,
      ),
    );

    if (result != null && mounted) {
      setState(() {
        _goal = result['goal'] as String;
        _dietType = result['dietType'] as String;
        _calories = result['calories'] as int;
        _mealsPerDay = result['mealsPerDay'] as int;
      });
    }
  }

  Future<void> _generate() async {
    final notifier = ref.read(generatePlanProvider.notifier);
    final plan = await notifier.generate({
      'goal': _goal,
      'diet_type': _dietType,
      'target_calories': _calories,
      'meals_per_day': _mealsPerDay,
    });
    if (!mounted) return;

    if (plan != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Meal plan generated!')),
      );
      ref.invalidate(mealPlansProvider);
      context.go('/nutrition');
    }
  }

  @override
  Widget build(BuildContext context) {
    final generateState = ref.watch(generatePlanProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('AI Meal Plan')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Your preferences',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 12),
                _PreferenceRow(
                  icon: Icons.flag,
                  label: 'Goal',
                  value: _formatGoal(_goal),
                ),
                _PreferenceRow(
                  icon: Icons.restaurant,
                  label: 'Diet type',
                  value: _formatDietType(_dietType),
                ),
                _PreferenceRow(
                  icon: Icons.local_fire_department,
                  label: 'Target calories',
                  value: '$_calories kcal',
                ),
                _PreferenceRow(
                  icon: Icons.event_note,
                  label: 'Meals per day',
                  value: '$_mealsPerDay',
                ),
                const SizedBox(height: 16),
                if (generateState.errorMessage != null) ...[
                  Text(
                    generateState.errorMessage!,
                    style: const TextStyle(color: AppTheme.error),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 12),
                ],
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: generateState.isLoading ? null : _openPreferences,
                        icon: const Icon(Icons.tune),
                        label: const Text('Edit'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: ElevatedButton.icon(
                        onPressed: generateState.isLoading ? null : _generate,
                        icon: generateState.isLoading
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            : const Icon(Icons.auto_awesome),
                        label: Text(
                          generateState.isLoading ? 'Generating…' : 'Generate',
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          const Text(
            '7-Day Overview',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 12),
          if (generateState.isLoading)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: CircularProgressIndicator(),
              ),
            )
          else
            _PlanGrid(plan: generateState.generatedPlan),
        ],
      ),
    );
  }

  String _formatGoal(String goal) {
    switch (goal) {
      case 'muscle_gain':
        return 'Muscle gain';
      case 'maintain':
        return 'Maintain';
      default:
        return 'Weight loss';
    }
  }

  String _formatDietType(String diet) {
    switch (diet) {
      case 'vegetarian':
        return 'Vegetarian';
      case 'vegan':
        return 'Vegan';
      case 'keto':
        return 'Keto';
      default:
        return 'Balanced';
    }
  }
}

class _PreferenceRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _PreferenceRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, color: AppTheme.primary, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              style: const TextStyle(color: AppTheme.textSecondary),
            ),
          ),
          Text(
            value,
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}

/// Shows the generated plan as a 7-day grid of meals, or an empty state.
class _PlanGrid extends StatelessWidget {
  final MealPlan? plan;
  const _PlanGrid({required this.plan});

  @override
  Widget build(BuildContext context) {
    if (plan == null) {
      return const EmptyState(
        icon: Icons.restaurant_menu,
        title: 'No plan yet',
        subtitle: 'Set your preferences and tap Generate.',
      );
    }

    return Column(
      children: [
        for (final day in plan!.days)
          AppCard(
            margin: const EdgeInsets.only(bottom: 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Day ${day.dayNumber}',
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(
                      '${day.totalCalories.round()} kcal',
                      style: const TextStyle(
                        color: AppTheme.textSecondary,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                if (day.items.isEmpty)
                  const Text(
                    'No meals for this day.',
                    style: TextStyle(color: AppTheme.textSecondary),
                  )
                else
                  for (final item in day.items)
                    _MealItemTile(item: item),
              ],
            ),
          ),
      ],
    );
  }
}

class _MealItemTile extends StatelessWidget {
  final MealPlanItem item;
  const _MealItemTile({required this.item});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: const BoxDecoration(
              color: AppTheme.primary,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.name,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                Text(
                  _capitalize(item.mealType),
                  style: const TextStyle(
                    color: AppTheme.textSecondary,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          if (item.calories != null)
            Text(
              '${item.calories!.round()} kcal',
              style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
            ),
        ],
      ),
    );
  }

  String _capitalize(String s) {
    if (s.isEmpty) return s;
    return s[0].toUpperCase() + s.substring(1);
  }
}

/// Bottom sheet for editing meal plan preferences.
class _PreferencesSheet extends StatefulWidget {
  final String goal;
  final String dietType;
  final int calories;
  final int mealsPerDay;

  const _PreferencesSheet({
    required this.goal,
    required this.dietType,
    required this.calories,
    required this.mealsPerDay,
  });

  @override
  State<_PreferencesSheet> createState() => _PreferencesSheetState();
}

class _PreferencesSheetState extends State<_PreferencesSheet> {
  late String _goal;
  late String _dietType;
  late int _calories;
  late int _mealsPerDay;

  @override
  void initState() {
    super.initState();
    _goal = widget.goal;
    _dietType = widget.dietType;
    _calories = widget.calories;
    _mealsPerDay = widget.mealsPerDay;
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 16,
        bottom: MediaQuery.of(context).viewInsets.bottom + 16,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Meal Plan Preferences',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 16),
          DropdownButtonFormField<String>(
            initialValue: _goal,
            decoration: const InputDecoration(labelText: 'Goal'),
            items: const [
              DropdownMenuItem(value: 'weight_loss', child: Text('Weight loss')),
              DropdownMenuItem(value: 'muscle_gain', child: Text('Muscle gain')),
              DropdownMenuItem(value: 'maintain', child: Text('Maintain')),
            ],
            onChanged: (v) => setState(() => _goal = v ?? 'weight_loss'),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            initialValue: _dietType,
            decoration: const InputDecoration(labelText: 'Diet type'),
            items: const [
              DropdownMenuItem(value: 'balanced', child: Text('Balanced')),
              DropdownMenuItem(value: 'vegetarian', child: Text('Vegetarian')),
              DropdownMenuItem(value: 'vegan', child: Text('Vegan')),
              DropdownMenuItem(value: 'keto', child: Text('Keto')),
            ],
            onChanged: (v) => setState(() => _dietType = v ?? 'balanced'),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<int>(
            initialValue: _calories,
            decoration: const InputDecoration(labelText: 'Target calories'),
            items: const [
              DropdownMenuItem(value: 1800, child: Text('1800 kcal')),
              DropdownMenuItem(value: 2000, child: Text('2000 kcal')),
              DropdownMenuItem(value: 2200, child: Text('2200 kcal')),
              DropdownMenuItem(value: 2500, child: Text('2500 kcal')),
            ],
            onChanged: (v) => setState(() => _calories = v ?? 2000),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<int>(
            initialValue: _mealsPerDay,
            decoration: const InputDecoration(labelText: 'Meals per day'),
            items: const [
              DropdownMenuItem(value: 3, child: Text('3 meals')),
              DropdownMenuItem(value: 4, child: Text('4 meals')),
              DropdownMenuItem(value: 5, child: Text('5 meals')),
            ],
            onChanged: (v) => setState(() => _mealsPerDay = v ?? 3),
          ),
          const SizedBox(height: 20),
          ElevatedButton(
            onPressed: () {
              Navigator.of(context).pop({
                'goal': _goal,
                'dietType': _dietType,
                'calories': _calories,
                'mealsPerDay': _mealsPerDay,
              });
            },
            child: const Text('Apply'),
          ),
        ],
      ),
    );
  }
}
