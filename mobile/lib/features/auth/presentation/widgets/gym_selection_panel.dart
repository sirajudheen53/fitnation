import 'package:flutter/material.dart';

import '../../../../core/errors/failures.dart';
import '../../../../core/theme/app_theme.dart';

/// "Specify your gym to continue" panel — shown when the backend cannot
/// disambiguate the account's gym during sign-in.
///
/// With a [gyms] list it renders a dropdown; without one it falls back to a
/// free-text field so the user can still type their gym name/ID.
class GymSelectionPanel extends StatefulWidget {
  final List<GymOption> gyms;
  final bool isBusy;
  final void Function(String gymId) onConfirm;

  const GymSelectionPanel({
    super.key,
    required this.gyms,
    required this.isBusy,
    required this.onConfirm,
  });

  @override
  State<GymSelectionPanel> createState() => _GymSelectionPanelState();
}

class _GymSelectionPanelState extends State<GymSelectionPanel> {
  String? _selectedGymId;
  final _manualController = TextEditingController();

  @override
  void dispose() {
    _manualController.dispose();
    super.dispose();
  }

  void _submit() {
    final gymId = widget.gyms.isNotEmpty
        ? _selectedGymId
        : _manualController.text.trim();
    if (gymId != null && gymId.isNotEmpty) {
      widget.onConfirm(gymId);
    }
  }

  @override
  Widget build(BuildContext context) {
    final canSubmit =
        !widget.isBusy &&
        (widget.gyms.isNotEmpty
            ? _selectedGymId != null
            : _manualController.text.trim().isNotEmpty);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Icon(
                Icons.store_outlined,
                color: AppTheme.primary,
                size: 20,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Specify your gym to continue',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Your account is linked to more than one gym. '
            'Pick the gym you want to sign in to.',
            style: Theme.of(context).textTheme.bodySmall
                ?.copyWith(color: AppTheme.textSecondary),
          ),
          const SizedBox(height: 12),
          if (widget.gyms.isNotEmpty)
            DropdownButtonFormField<String>(
              initialValue: _selectedGymId,
              isExpanded: true,
              hint: const Text('Select your gym'),
              items: [
                for (final gym in widget.gyms)
                  DropdownMenuItem(value: gym.id, child: Text(gym.name)),
              ],
              onChanged: (value) => setState(() => _selectedGymId = value),
            )
          else
            TextField(
              controller: _manualController,
              textInputAction: TextInputAction.done,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(
                labelText: 'Gym name or ID',
                hintText: 'e.g. FitNation Koramangala',
              ),
            ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: canSubmit ? _submit : null,
            child: widget.isBusy
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Text('Continue'),
          ),
        ],
      ),
    );
  }
}
