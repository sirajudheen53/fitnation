import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../auth/presentation/providers/auth_notifier.dart';
import '../providers/attendance_provider.dart';

/// QR check-in screen.
///
/// Note: A full camera-based QR scanner requires the `mobile_scanner` or
/// `qr_code_scanner` package. This screen provides a manual QR code entry
/// fallback and a placeholder for the camera scanner, so the flow works
/// end-to-end without adding native dependencies.
class QrCheckInScreen extends ConsumerStatefulWidget {
  const QrCheckInScreen({super.key});

  @override
  ConsumerState<QrCheckInScreen> createState() => _QrCheckInScreenState();
}

class _QrCheckInScreenState extends ConsumerState<QrCheckInScreen> {
  final _qrController = TextEditingController();

  @override
  void dispose() {
    _qrController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final qrCode = _qrController.text.trim();
    if (qrCode.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter or scan the QR code')),
      );
      return;
    }

    final customerId = ref.read(authProvider).user?.id;
    final success = await ref
        .read(checkInProvider.notifier)
        .checkIn(qrCode, customerId: customerId);

    if (!mounted) return;

    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Check-in successful! Welcome to the gym!')),
      );
      ref.invalidate(attendanceHistoryProvider);
      context.pop();
    } else {
      final error = ref.read(checkInProvider).errorMessage;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error ?? 'Check-in failed')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final checkInState = ref.watch(checkInProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('QR Check-in')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Spacer(flex: 1),
              // Scanner placeholder
              Container(
                height: 220,
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: AppTheme.primary, width: 2),
                ),
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.qr_code_scanner, size: 64, color: AppTheme.primary),
                      const SizedBox(height: 12),
                      Text(
                        'Camera scanner coming soon',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        'Enter the QR code manually below',
                        style: TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
              TextField(
                controller: _qrController,
                decoration: const InputDecoration(
                  labelText: 'QR Code',
                  hintText: 'Scan or enter the gym QR code',
                  prefixIcon: Icon(Icons.qr_code),
                ),
                textInputAction: TextInputAction.done,
                onSubmitted: (_) => _submit(),
              ),
              if (checkInState.errorMessage != null) ...[
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.error.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    checkInState.errorMessage!,
                    style: const TextStyle(color: AppTheme.error, fontSize: 13),
                  ),
                ),
              ],
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: checkInState.isLoading ? null : _submit,
                child: checkInState.isLoading
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Text('Check In'),
              ),
              const Spacer(flex: 2),
            ],
          ),
        ),
      ),
    );
  }
}
