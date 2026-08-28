import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/async_view.dart';
import '../../data/models/body_measurement.dart';
import '../providers/progress_provider.dart';

/// Shows the customer's body measurements and weight tracking.
class ProgressScreen extends ConsumerWidget {
  const ProgressScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final measurementsAsync = ref.watch(bodyMeasurementsProvider);
    final goalsAsync = ref.watch(fitnessGoalsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Progress'),
        actions: [
          IconButton(
            icon: const Icon(Icons.photo_library_outlined),
            onPressed: () => context.push('/progress/photos'),
            tooltip: 'Progress Photos',
          ),
        ],
      ),
      body: AsyncView<List<BodyMeasurement>>(
        value: measurementsAsync,
        onRetry: () => ref.invalidate(bodyMeasurementsProvider),
        builder: (measurements) {
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Latest stats
              _LatestStats(measurements: measurements),
              const SizedBox(height: 24),
              // Weight trend
              Text(
                'Weight Trend',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 12),
              _WeightChart(measurements: measurements),
              const SizedBox(height: 24),
              // Goals
              Text(
                'Fitness Goals',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 12),
              AsyncView<List<FitnessGoal>>(
                value: goalsAsync,
                onRetry: () => ref.invalidate(fitnessGoalsProvider),
                builder: (goals) {
                  if (goals.isEmpty) {
                    return const EmptyState(
                      icon: Icons.flag_outlined,
                      title: 'No goals set',
                      subtitle: 'Your trainer will set goals for you.',
                    );
                  }
                  return Column(
                    children: [
                      for (final goal in goals) _GoalCard(goal: goal),
                    ],
                  );
                },
              ),
            ],
          );
        },
      ),
    );
  }
}

class _LatestStats extends StatelessWidget {
  final List<BodyMeasurement> measurements;

  const _LatestStats({required this.measurements});

  @override
  Widget build(BuildContext context) {
    if (measurements.isEmpty) {
      return const EmptyState(
        icon: Icons.monitor_weight_outlined,
        title: 'No measurements yet',
        subtitle: 'Your measurements will appear here once recorded.',
      );
    }

    final latest = measurements.first;
    final previous = measurements.length > 1 ? measurements[1] : null;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Latest Measurements',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _Metric(
                label: 'Weight',
                value: latest.weight != null ? '${latest.weight!.toStringAsFixed(1)} kg' : '—',
                delta: _delta(latest.weight, previous?.weight),
              ),
              _Metric(
                label: 'BMI',
                value: latest.bmi != null ? latest.bmi!.toStringAsFixed(1) : '—',
                delta: _delta(latest.bmi, previous?.bmi),
              ),
              _Metric(
                label: 'Body Fat',
                value: latest.bodyFat != null ? '${latest.bodyFat!.toStringAsFixed(1)}%' : '—',
                delta: _delta(latest.bodyFat, previous?.bodyFat),
              ),
            ],
          ),
        ],
      ),
    );
  }

  String? _delta(double? current, double? previous) {
    if (current == null || previous == null) return null;
    final diff = current - previous;
    if (diff == 0) return '±0';
    return diff > 0 ? '+${diff.toStringAsFixed(1)}' : diff.toStringAsFixed(1);
  }
}

class _Metric extends StatelessWidget {
  final String label;
  final String value;
  final String? delta;

  const _Metric({required this.label, required this.value, this.delta});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: AppTheme.primary),
        ),
        const SizedBox(height: 4),
        Text(label, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
        if (delta != null)
          Text(
            delta!,
            style: TextStyle(
              fontSize: 11,
              color: delta!.startsWith('+') ? AppTheme.error : AppTheme.accent,
            ),
          ),
      ],
    );
  }
}

class _WeightChart extends StatelessWidget {
  final List<BodyMeasurement> measurements;

  const _WeightChart({required this.measurements});

  @override
  Widget build(BuildContext context) {
    final weights = measurements
        .where((m) => m.weight != null)
        .take(10)
        .toList()
        .reversed
        .toList();

    if (weights.isEmpty) {
      return const AppCard(
        child: Text(
          'No weight data available',
          style: TextStyle(color: AppTheme.textSecondary),
        ),
      );
    }

    final spots = <FlSpot>[
      for (var i = 0; i < weights.length; i++)
        FlSpot(i.toDouble(), weights[i].weight!),
    ];

    final maxWeight = weights.map((m) => m.weight!).reduce((a, b) => a > b ? a : b);
    final minWeight = weights.map((m) => m.weight!).reduce((a, b) => a < b ? a : b);
    final padding = (maxWeight - minWeight).clamp(1.0, double.infinity) * 0.2;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            height: 200,
            child: LineChart(
              LineChartData(
                minY: (minWeight - padding).floorToDouble(),
                maxY: (maxWeight + padding).ceilToDouble(),
                gridData: FlGridData(
                  show: true,
                  drawVerticalLine: false,
                  getDrawingHorizontalLine: (value) => FlLine(
                    color: AppTheme.divider,
                    strokeWidth: 1,
                  ),
                ),
                titlesData: FlTitlesData(
                  topTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false),
                  ),
                  rightTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false),
                  ),
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 40,
                      getTitlesWidget: (value, meta) => Text(
                        value.toStringAsFixed(0),
                        style: const TextStyle(
                          color: AppTheme.textSecondary,
                          fontSize: 10,
                        ),
                      ),
                    ),
                  ),
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 28,
                      interval: 1,
                      getTitlesWidget: (value, meta) {
                        final index = value.toInt();
                        if (index < 0 || index >= weights.length) {
                          return const SizedBox.shrink();
                        }
                        return Padding(
                          padding: const EdgeInsets.only(top: 6),
                          child: Text(
                            _shortDate(weights[index].measuredAt),
                            style: const TextStyle(
                              color: AppTheme.textSecondary,
                              fontSize: 10,
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ),
                borderData: FlBorderData(show: false),
                lineBarsData: [
                  LineChartBarData(
                    spots: spots,
                    isCurved: true,
                    color: AppTheme.primary,
                    barWidth: 3,
                    dotData: FlDotData(
                      show: true,
                      getDotPainter: (spot, percent, barData, index) =>
                          FlDotCirclePainter(
                        radius: 4,
                        color: AppTheme.primary,
                        strokeWidth: 2,
                        strokeColor: AppTheme.surface,
                      ),
                    ),
                    belowBarData: BarAreaData(
                      show: true,
                      gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: [
                          AppTheme.primary.withValues(alpha: 0.25),
                          AppTheme.primary.withValues(alpha: 0.0),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _shortDate(DateTime? date) {
    if (date == null) return '—';
    return '${date.day}/${date.month}';
  }
}

class _GoalCard extends StatelessWidget {
  final FitnessGoal goal;

  const _GoalCard({required this.goal});

  @override
  Widget build(BuildContext context) {
    final progress = goal.progressPercentage;
    final target = goal.targetValue ?? goal.targetWeight;

    return AppCard(
      margin: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: AppTheme.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.flag, color: AppTheme.primary, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      goal.goalType ?? 'Goal',
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    if (goal.description != null)
                      Text(
                        goal.description!,
                        style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                      ),
                    if (target != null)
                      Text(
                        'Target: ${target.toStringAsFixed(1)} ${goal.targetUnit ?? 'kg'}',
                        style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
                      ),
                  ],
                ),
              ),
              if (goal.status != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppTheme.accent.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    goal.status!,
                    style: const TextStyle(
                      color: AppTheme.accent,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
            ],
          ),
          if (progress != null) ...[
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(
                value: (progress / 100).clamp(0.0, 1.0),
                minHeight: 8,
                backgroundColor: AppTheme.background,
                color: AppTheme.primary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              '${progress.toStringAsFixed(0)}% complete',
              style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
            ),
          ],
        ],
      ),
    );
  }
}
