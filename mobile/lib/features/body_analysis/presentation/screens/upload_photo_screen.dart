import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_card.dart';
import '../providers/body_analysis_provider.dart';

/// Photo upload screen for body analysis.
/// Lets the user pick a source (camera/gallery) and a view type.
class UploadPhotoScreen extends ConsumerStatefulWidget {
  const UploadPhotoScreen({super.key});

  @override
  ConsumerState<UploadPhotoScreen> createState() => _UploadPhotoScreenState();
}

class _UploadPhotoScreenState extends ConsumerState<UploadPhotoScreen> {
  String _photoType = 'front';
  String? _selectedImagePath;

  final List<Map<String, String>> _typeOptions = [
    {'value': 'front', 'label': 'Front', 'icon': '😀'},
    {'value': 'side', 'label': 'Side', 'icon': '↔️'},
    {'value': 'back', 'label': 'Back', 'icon': '🙃'},
  ];

  void _selectType(String value) {
    setState(() => _photoType = value);
  }

  /// Simulates picking from the camera/gallery.
  /// In a full implementation this would invoke image_picker.
  Future<void> _pickImage(String source) async {
    // Placeholder: image_picker would return a file path here.
    setState(() => _selectedImagePath = source == 'camera' ? '/camera/capture.jpg' : '/gallery/selected.jpg');
  }

  Future<void> _submit() async {
    if (_selectedImagePath == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select a photo first.')),
      );
      return;
    }
    final success = await ref
        .read(uploadProvider.notifier)
        .upload(_selectedImagePath!, _photoType);
    if (!mounted) return;

    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Photo uploaded for analysis!')),
      );
      ref.invalidate(bodyAnalysesProvider);
      context.pop();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Upload failed. Please try again.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final uploadState = ref.watch(uploadProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Upload Photo')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Preview / placeholder
          AppCard(
            child: _selectedImagePath == null
                ? const Column(
                    children: [
                      SizedBox(height: 24),
                      Icon(Icons.add_a_photo, size: 64, color: AppTheme.textSecondary),
                      SizedBox(height: 12),
                      Text(
                        'No photo selected',
                        style: TextStyle(color: AppTheme.textSecondary),
                      ),
                      SizedBox(height: 24),
                    ],
                  )
                : Column(
                    children: [
                      const SizedBox(height: 24),
                      Icon(Icons.check_circle, size: 64, color: AppTheme.accent),
                      const SizedBox(height: 12),
                      const Text('Photo ready to upload'),
                      const SizedBox(height: 24),
                    ],
                  ),
          ),
          const SizedBox(height: 16),

          // Source picker
          const Text('Photo source', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: uploadState.isLoading ? null : () => _pickImage('camera'),
                  icon: const Icon(Icons.photo_camera),
                  label: const Text('Camera'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: uploadState.isLoading ? null : () => _pickImage('gallery'),
                  icon: const Icon(Icons.photo_library),
                  label: const Text('Gallery'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),

          // Photo type selector
          const Text('Photo type', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          Row(
            children: [
              for (final option in _typeOptions) ...[
                Expanded(
                  child: _TypeOption(
                    label: option['label']!,
                    icon: option['icon']!,
                    selected: _photoType == option['value'],
                    onTap: uploadState.isLoading
                        ? null
                        : () => _selectType(option['value']!),
                  ),
                ),
                if (option['value'] != 'back') const SizedBox(width: 8),
              ],
            ],
          ),
          const SizedBox(height: 32),

          if (uploadState.errorMessage != null) ...[
            Text(
              uploadState.errorMessage!,
              style: const TextStyle(color: AppTheme.error),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
          ],

          ElevatedButton.icon(
            onPressed: uploadState.isLoading ? null : _submit,
            icon: uploadState.isLoading
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.cloud_upload),
            label: Text(uploadState.isLoading ? 'Uploading…' : 'Submit'),
          ),
        ],
      ),
    );
  }
}

class _TypeOption extends StatelessWidget {
  final String label;
  final String icon;
  final bool selected;
  final VoidCallback? onTap;

  const _TypeOption({
    required this.label,
    required this.icon,
    required this.selected,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: selected
              ? AppTheme.primary.withValues(alpha: 0.1)
              : AppTheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: selected ? AppTheme.primary : AppTheme.divider,
            width: selected ? 2 : 1,
          ),
        ),
        child: Column(
          children: [
            Text(icon, style: const TextStyle(fontSize: 24)),
            const SizedBox(height: 6),
            Text(
              label,
              style: TextStyle(
                color: selected ? AppTheme.primary : AppTheme.textPrimary,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
