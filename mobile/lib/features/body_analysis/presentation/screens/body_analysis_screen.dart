import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/async_view.dart';
import '../../models/body_analysis.dart';
import '../../models/progress_log.dart';
import '../providers/body_analysis_provider.dart';

/// Body Analysis dashboard showing past analyses, upload entry, and progress.
class BodyAnalysisScreen extends ConsumerWidget {
  const BodyAnalysisScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final analysesAsync = ref.watch(bodyAnalysesProvider);
    final progressAsync = ref.watch(bodyProgressProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Body Analysis')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _UploadButton(
            onTap: () => context.push('/body-analysis/upload'),
          ),
          const SizedBox(height: 24),
          const SectionHeader(title: 'Progress'),
          const SizedBox(height: 12),
          AsyncView<List<ProgressLog>>(
            value: progressAsync,
            onRetry: () => ref.invalidate(bodyProgressProvider),
            builder: (logs) => _ProgressChart(logs: logs),
          ),
          const SizedBox(height: 24),
          const SectionHeader(title: 'Past Analyses'),
          const SizedBox(height: 12),
          AsyncView<List<BodyAnalysis>>(
            value: analysesAsync,
            onRetry: () => ref.invalidate(bodyAnalysesProvider),
            builder: (analyses) => _AnalysesList(analyses: analyses),
          ),
        ],
      ),
    );
  }
}

class _UploadButton extends StatelessWidget {
  final VoidCallback onTap;
  const _UploadButton({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      color: AppTheme.primary,
      onTap: onTap,
      child: const Row(
        children: [
          Icon(Icons.add_a_photo, color: Colors.white, size: 32),
          SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Upload a new photo',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                SizedBox(height: 4),
                Text(
                  'Get instant BMI, body fat and posture analysis',
                  style: TextStyle(color: Colors.white70, fontSize: 13),
                ),
              ],
            ),
          ),
          Icon(Icons.chevron_right, color: Colors.white, size: 28),
        ],
      ),
    );
  }
}

class _ProgressChart extends StatelessWidget {
  final List<ProgressLog> logs;
  const _ProgressChart({required this.logs});

  @override
  Widget build(BuildContext context) {
    if (logs.isEmpty) {
      return const EmptyState(
        icon: Icons.show_chart,
        title: 'No progress data yet',
        subtitle: 'Upload photos to start tracking your weight over time.',
      );
    }

    // Simple bar chart built from the weight logs.
    final sorted = [...logs]
      ..sort((a, b) => (a.loggedAt ?? DateTime.fromMillisecondsSinceEpoch(0))
          .compareTo(b.loggedAt ?? DateTime.fromMillisecondsSinceEpoch(0)));
    final maxWeight =
        sorted.map((l) => l.weight).reduce((a, b) => a > b ? a : b) * 1.1;
    final minWeight =
        sorted.map((l) => l.weight).reduce((a, b) => a < b ? a : b) * 0.9;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Weight over time',
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 160,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                for (final log in sorted)
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.end,
                        children: [
                          Text(
                            '${log.weight.round()}',
                            style: const TextStyle(
                              fontSize: 10,
                              color: AppTheme.textSecondary,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Container(
                            height: ((log.weight - minWeight) /
                                    (maxWeight - minWeight))
                                .clamp(0.05, 1.0) *
                                110,
                            decoration: BoxDecoration(
                              color: AppTheme.primary,
                              borderRadius: BorderRadius.circular(6),
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            '${log.loggedAt?.day ?? ''}',
                            style: const TextStyle(
                              fontSize: 10,
                              color: AppTheme.textSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _AnalysesList extends StatelessWidget {
  final List<BodyAnalysis> analyses;
  const _AnalysesList({required this.analyses});

  @override
  Widget build(BuildContext context) {
    if (analyses.isEmpty) {
      return const EmptyState(
        icon: Icons.monitor_weight_outlined,
        title: 'No analyses yet',
        subtitle: 'Upload a photo to get your first body analysis.',
      );
    }

    return Column(
      children: [
        for (final analysis in analyses) _AnalysisCard(analysis: analysis),
      ],
    );
  }
}

class _AnalysisCard extends StatelessWidget {
  final BodyAnalysis analysis;
  const _AnalysisCard({required this.analysis});

  @override
  Widget build(BuildContext context) {
    final date = analysis.analyzedAt != null
        ? '${analysis.analyzedAt!.day}/${analysis.analyzedAt!.month}/${analysis.analyzedAt!.year}'
        : 'Recent';

    return AppCard(
      margin: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                date,
                style: const TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 13,
                ),
              ),
              if (analysis.status != null)
                Chip(
                  label: Text(analysis.status!),
                  labelStyle: const TextStyle(fontSize: 12),
                  visualDensity: VisualDensity.compact,
                  backgroundColor: AppTheme.accent.withValues(alpha: 0.12),
                ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _Metric(
                icon: Icons.monitor_weight,
                label: 'BMI',
                value: analysis.bmi?.toStringAsFixed(1) ?? '—',
              ),
              _Metric(
                icon: Icons.percent,
                label: 'Body Fat',
                value: analysis.bodyFatPercentage != null
                    ? '${analysis.bodyFatPercentage!.toStringAsFixed(1)}%'
                    : '—',
              ),
              _Metric(
                icon: Icons.accessibility_new,
                label: 'Posture',
                value: analysis.postureScore?.toStringAsFixed(0) ?? '—',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  const _Metric({
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Icon(icon, color: AppTheme.primary, size: 22),
          const SizedBox(height: 6),
          Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
        ],
      ),
    );
  }
}
