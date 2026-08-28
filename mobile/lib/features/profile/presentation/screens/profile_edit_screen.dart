import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/widgets/async_view.dart';
import '../../../auth/presentation/providers/auth_notifier.dart';
import '../../data/models/customer_profile.dart';
import '../providers/profile_provider.dart';

/// Allows the customer to edit their profile and health information.
class ProfileEditScreen extends ConsumerStatefulWidget {
  const ProfileEditScreen({super.key});

  @override
  ConsumerState<ProfileEditScreen> createState() => _ProfileEditScreenState();
}

class _ProfileEditScreenState extends ConsumerState<ProfileEditScreen> {
  final _formKey = GlobalKey<FormState>();

  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  final _emergencyContactController = TextEditingController();
  final _emergencyPhoneController = TextEditingController();
  final _addressController = TextEditingController();
  final _heightController = TextEditingController();
  final _weightController = TextEditingController();
  final _bloodGroupController = TextEditingController();

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    _emergencyContactController.dispose();
    _emergencyPhoneController.dispose();
    _addressController.dispose();
    _heightController.dispose();
    _weightController.dispose();
    _bloodGroupController.dispose();
    super.dispose();
  }

  void _prefill(CustomerProfile? profile, HealthProfile? health) {
    if (_nameController.text.isEmpty && profile != null) {
      _nameController.text = profile.fullName;
      _phoneController.text = profile.phone ?? '';
      _emergencyContactController.text = profile.emergencyContact ?? '';
      _emergencyPhoneController.text = profile.emergencyPhone ?? '';
      _addressController.text = profile.fullAddress ?? '';
    }
    if (_heightController.text.isEmpty && health != null) {
      _heightController.text =
          health.height != null ? health.height!.toStringAsFixed(1) : '';
      _weightController.text =
          health.weight != null ? health.weight!.toStringAsFixed(1) : '';
      _bloodGroupController.text = health.bloodGroup ?? '';
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;

    final customerId = ref.read(authProvider).user?.id;
    if (customerId == null) return;

    final notifier = ref.read(profileEditProvider.notifier);

    final profileData = <String, dynamic>{
      'name': _nameController.text.trim(),
      'phone': _phoneController.text.trim(),
      'emergency_contact_name': _emergencyContactController.text.trim(),
      'emergency_contact_phone': _emergencyPhoneController.text.trim(),
      'address_street': _addressController.text.trim(),
    };

    final healthData = <String, dynamic>{
      if (_heightController.text.trim().isNotEmpty)
        'height_cm': double.tryParse(_heightController.text.trim()),
      if (_weightController.text.trim().isNotEmpty)
        'weight_kg': double.tryParse(_weightController.text.trim()),
      if (_bloodGroupController.text.trim().isNotEmpty)
        'blood_group': _bloodGroupController.text.trim(),
    };

    final profileOk = await notifier.updateProfile(customerId, profileData);
    if (!profileOk) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              ref.read(profileEditProvider).errorMessage ?? 'Failed to save profile',
            ),
          ),
        );
      }
      return;
    }

    if (healthData.isNotEmpty) {
      final healthOk = await notifier.updateHealthProfile(customerId, healthData);
      if (!healthOk) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                ref.read(profileEditProvider).errorMessage ??
                    'Failed to save health profile',
              ),
            ),
          );
        }
        return;
      }
    }

    // Refresh the profile providers and pop back.
    ref.invalidate(customerProfileProvider);
    ref.invalidate(healthProfileProvider);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Profile updated')),
      );
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final profileAsync = ref.watch(customerProfileProvider);
    final healthAsync = ref.watch(healthProfileProvider);
    final editState = ref.watch(profileEditProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Edit Profile')),
      body: AsyncView<CustomerProfile?>(
        value: profileAsync,
        onRetry: () => ref.invalidate(customerProfileProvider),
        builder: (profile) {
          final health = healthAsync.valueOrNull;
          _prefill(profile, health);

          return Form(
            key: _formKey,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  'Personal Information',
                  style: Theme.of(context)
                      .textTheme
                      .titleLarge
                      ?.copyWith(fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _nameController,
                  decoration: const InputDecoration(labelText: 'Full Name'),
                  textCapitalization: TextCapitalization.words,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _phoneController,
                  decoration: const InputDecoration(labelText: 'Phone'),
                  keyboardType: TextInputType.phone,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _emergencyContactController,
                  decoration: const InputDecoration(labelText: 'Emergency Contact'),
                  textCapitalization: TextCapitalization.words,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _emergencyPhoneController,
                  decoration: const InputDecoration(labelText: 'Emergency Phone'),
                  keyboardType: TextInputType.phone,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _addressController,
                  decoration: const InputDecoration(labelText: 'Address'),
                ),
                const SizedBox(height: 24),
                Text(
                  'Health Information',
                  style: Theme.of(context)
                      .textTheme
                      .titleLarge
                      ?.copyWith(fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _heightController,
                  decoration: const InputDecoration(
                    labelText: 'Height (cm)',
                    suffixText: 'cm',
                  ),
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) return null;
                    final parsed = double.tryParse(value.trim());
                    if (parsed == null || parsed <= 0) {
                      return 'Enter a valid height';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _weightController,
                  decoration: const InputDecoration(
                    labelText: 'Weight (kg)',
                    suffixText: 'kg',
                  ),
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) return null;
                    final parsed = double.tryParse(value.trim());
                    if (parsed == null || parsed <= 0) {
                      return 'Enter a valid weight';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _bloodGroupController,
                  decoration: const InputDecoration(labelText: 'Blood Group'),
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: editState.isSaving ? null : _save,
                  child: editState.isSaving
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Text('Save Changes'),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
