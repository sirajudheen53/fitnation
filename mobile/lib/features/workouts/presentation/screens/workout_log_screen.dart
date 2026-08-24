import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../auth/presentation/providers/auth_notifier.dart';
import '../../data/models/workout_log.dart';
import '../../data/models/workout_plan.dart';
import '../providers/workout_provider.dart';

/// Screen for logging a completed workout (weight, reps, rest per set).
class WorkoutLogScreen extends ConsumerStatefulWidget {
  final WorkoutPlan plan;
  final WorkoutDay day;

  const WorkoutLogScreen({
    super.key,
    required this.plan,
    required this.day,
  });

  @override
  ConsumerState<WorkoutLogScreen> createState() => _WorkoutLogScreenState();
}

class _WorkoutLogScreenState extends ConsumerState<WorkoutLogScreen> {
  final Map<int, List<TextEditingController>> _weightControllers = {};
  final Map<int, List<TextEditingController>> _repsControllers = {};
  final Map<int, List<TextEditingController>> _restControllers = {};
  final Map<int, List<bool>> _completed = {};
  final _durationController = TextEditingController();
  final _notesController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _initControllers();
  }

  void _initControllers() {
    for (final we in widget.day.exercises) {
      final targetSets = we.targetSets ?? we.sets.length;
      final setCount = targetSets > 0 ? targetSets : 1;
      _weightControllers[we.exercise.id] =
          List.generate(setCount, (_) => TextEditingController());
      _repsControllers[we.exercise.id] =
          List.generate(setCount, (_) => TextEditingController());
      _restControllers[we.exercise.id] =
          List.generate(setCount, (_) => TextEditingController());
      _completed[we.exercise.id] = List.generate(setCount, (_) => false);
    }
  }

  @override
  void dispose() {
    for (final list in _weightControllers.values) {
      for (final c in list) {
        c.dispose();
      }
    }
    for (final list in _repsControllers.values) {
      for (final c in list) {
        c.dispose();
      }
    }
    for (final list in _restControllers.values) {
      for (final c in list) {
        c.dispose();
      }
    }
    _durationController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final customerId = ref.read(authProvider).user?.id;
    final sets = <LoggedSet>[];

    for (final we in widget.day.exercises) {
      final weights = _weightControllers[we.exercise.id]!;
      final reps = _repsControllers[we.exercise.id]!;
      final rests = _restControllers[we.exercise.id]!;
      final completed = _completed[we.exercise.id]!;

      for (var i = 0; i < weights.length; i++) {
        if (!completed[i]) continue;
        sets.add(LoggedSet(
          exerciseId: we.exercise.id,
          setNumber: i + 1,
          weight: double.tryParse(weights[i].text),
          reps: int.tryParse(reps[i].text),
          restSeconds: int.tryParse(rests[i].text),
          isCompleted: true,
        ));
      }
    }

    if (sets.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Mark at least one set as completed')),
      );
      return;
    }

    final log = WorkoutLog(
      customerId: customerId,
      planId: widget.plan.id,
      dayId: widget.day.id,
      durationMinutes: int.tryParse(_durationController.text),
      notes: _notesController.text.isEmpty ? null : _notesController.text,
      sets: sets,
    );

    final success = await ref.read(workoutLogProvider.notifier).logWorkout(log);

    if (!mounted) return;

    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Workout logged successfully!')),
      );
      context.pop();
    } else {
      final error = ref.read(workoutLogProvider).errorMessage;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error ?? 'Failed to log workout')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final logState = ref.watch(workoutLogProvider);

    return Scaffold(
      appBar: AppBar(title: Text('Log ${widget.day.name}')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          for (final we in widget.day.exercises) _buildExerciseSection(we),
          const SizedBox(height: 16),
          // Duration
          TextField(
            controller: _durationController,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Duration (minutes)',
              prefixIcon: Icon(Icons.timer_outlined),
            ),
          ),
          const SizedBox(height: 12),
          // Notes
          TextField(
            controller: _notesController,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'Notes',
              prefixIcon: Icon(Icons.notes),
            ),
          ),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: logState.isLoading ? null : _submit,
            child: logState.isLoading
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Text('Submit Workout Log'),
          ),
        ],
      ),
    );
  }

  Widget _buildExerciseSection(WorkoutExercise we) {
    final weights = _weightControllers[we.exercise.id]!;
    final reps = _repsControllers[we.exercise.id]!;
    final rests = _restControllers[we.exercise.id]!;
    final completed = _completed[we.exercise.id]!;

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            we.exercise.name,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 12),
          // Header row
          const Row(
            children: [
              SizedBox(width: 40, child: Text('Set', style: TextStyle(fontSize: 12))),
              Expanded(child: Text('Weight (kg)', style: TextStyle(fontSize: 12))),
              Expanded(child: Text('Reps', style: TextStyle(fontSize: 12))),
              Expanded(child: Text('Rest (s)', style: TextStyle(fontSize: 12))),
              SizedBox(width: 40),
            ],
          ),
          const SizedBox(height: 8),
          for (var i = 0; i < weights.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  SizedBox(
                    width: 40,
                    child: Text('${i + 1}', style: const TextStyle(fontWeight: FontWeight.w600)),
                  ),
                  Expanded(
                    child: _smallField(weights[i], 'kg'),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _smallField(reps[i], 'reps'),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _smallField(rests[i], 's'),
                  ),
                  const SizedBox(width: 8),
                  Checkbox(
                    value: completed[i],
                    onChanged: (v) => setState(() => completed[i] = v ?? false),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _smallField(TextEditingController controller, String hint) {
    return TextField(
      controller: controller,
      keyboardType: TextInputType.number,
      textAlign: TextAlign.center,
      decoration: InputDecoration(
        hintText: hint,
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AppTheme.divider),
        ),
      ),
    );
  }
}
