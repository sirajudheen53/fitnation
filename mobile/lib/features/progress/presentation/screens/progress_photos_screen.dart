import 'package:flutter/material.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/async_view.dart';
import '../../data/models/body_measurement.dart';
import '../providers/progress_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Shows the customer's progress photos gallery.
class ProgressPhotosScreen extends ConsumerWidget {
  const ProgressPhotosScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Progress photos are not yet exposed via a dedicated endpoint.
    // We derive a placeholder gallery from measurements for now.
    final measurementsAsync = ref.watch(bodyMeasurementsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Progress Photos')),
      body: AsyncView<List<BodyMeasurement>>(
        value: measurementsAsync,
        onRetry: () => ref.invalidate(bodyMeasurementsProvider),
        builder: (measurements) {
          if (measurements.isEmpty) {
            return const EmptyState(
              icon: Icons.photo_library_outlined,
              title: 'No progress photos yet',
              subtitle: 'Photos will appear here once uploaded.',
            );
          }

          return GridView.builder(
            padding: const EdgeInsets.all(16),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              childAspectRatio: 0.8,
            ),
            itemCount: measurements.length,
            itemBuilder: (context, index) {
              final m = measurements[index];
              return _PhotoCard(measurement: m);
            },
          );
        },
      ),
    );
  }
}

class _PhotoCard extends StatelessWidget {
  final BodyMeasurement measurement;

  const _PhotoCard({required this.measurement});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: AppTheme.primary.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.person, size: 48, color: AppTheme.primary),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            _formatDate(measurement.measuredAt),
            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
          ),
          if (measurement.weight != null)
            Text(
              '${measurement.weight!.toStringAsFixed(1)} kg',
              style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
            ),
        ],
      ),
    );
  }

  String _formatDate(DateTime? date) {
    if (date == null) return 'Unknown date';
    return '${date.day}/${date.month}/${date.year}';
  }
}
