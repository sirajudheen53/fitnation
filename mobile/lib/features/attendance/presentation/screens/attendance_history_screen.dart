import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/async_view.dart';
import '../../data/models/attendance_record.dart';
import '../providers/attendance_provider.dart';

/// Shows the customer's attendance history.
class AttendanceHistoryScreen extends ConsumerWidget {
  const AttendanceHistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final historyAsync = ref.watch(attendanceHistoryProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Attendance'),
        actions: [
          IconButton(
            icon: const Icon(Icons.qr_code_scanner),
            onPressed: () => context.push('/attendance/checkin'),
          ),
        ],
      ),
      body: AsyncView<List<AttendanceRecord>>(
        value: historyAsync,
        onRetry: () => ref.invalidate(attendanceHistoryProvider),
        builder: (records) {
          if (records.isEmpty) {
            return const EmptyState(
              icon: Icons.event_available,
              title: 'No attendance records yet',
              subtitle: 'Check in at the gym to start your streak!',
            );
          }

          final streak = _calculateStreak(records);

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Streak card
              AppCard(
                child: Row(
                  children: [
                    Container(
                      width: 56,
                      height: 56,
                      decoration: BoxDecoration(
                        color: AppTheme.primary.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: const Icon(Icons.local_fire_department, color: AppTheme.primary, size: 32),
                    ),
                    const SizedBox(width: 16),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '$streak day${streak == 1 ? '' : 's'}',
                          style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
                        ),
                        const Text(
                          'Current streak',
                          style: TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              Text(
                'History',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 12),
              for (final record in records) _RecordTile(record: record),
            ],
          );
        },
      ),
    );
  }

  /// Calculates the current consecutive-day streak from attendance records.
  int _calculateStreak(List<AttendanceRecord> records) {
    final days = records
        .map((r) => r.checkInTime)
        .whereType<DateTime>()
        .map((d) => DateTime(d.year, d.month, d.day))
        .toSet()
        .toList()
      ..sort((a, b) => b.compareTo(a));

    if (days.isEmpty) return 0;

    var streak = 1;
    var expected = days.first.subtract(const Duration(days: 1));

    for (final day in days.skip(1)) {
      if (day == expected) {
        streak++;
        expected = expected.subtract(const Duration(days: 1));
      } else {
        break;
      }
    }

    return streak;
  }
}

class _RecordTile extends StatelessWidget {
  final AttendanceRecord record;

  const _RecordTile({required this.record});

  @override
  Widget build(BuildContext context) {
    final time = record.checkInTime;
    final isToday = record.isToday;

    return AppCard(
      margin: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: (isToday ? AppTheme.accent : AppTheme.primary).withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(
              isToday ? Icons.check_circle : Icons.event_available,
              color: isToday ? AppTheme.accent : AppTheme.primary,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _formatDate(time),
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                if (time != null)
                  Text(
                    _formatTime(time),
                    style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                  ),
              ],
            ),
          ),
          if (isToday)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AppTheme.accent.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Text(
                'Today',
                style: TextStyle(color: AppTheme.accent, fontSize: 12, fontWeight: FontWeight.w600),
              ),
            ),
        ],
      ),
    );
  }

  String _formatDate(DateTime? time) {
    if (time == null) return 'Unknown date';
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    return '${time.day} ${months[time.month - 1]} ${time.year}';
  }

  String _formatTime(DateTime time) {
    final hour = time.hour;
    final minute = time.minute.toString().padLeft(2, '0');
    final period = hour >= 12 ? 'PM' : 'AM';
    final displayHour = hour % 12 == 0 ? 12 : hour % 12;
    return '$displayHour:$minute $period';
  }
}
