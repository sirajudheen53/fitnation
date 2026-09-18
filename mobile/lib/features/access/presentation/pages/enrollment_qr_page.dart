import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../auth/presentation/providers/auth_notifier.dart';
import '../../data/models/enrollment_qr_payload.dart';

/// Enrollment QR screen.
///
/// Shows a QR code encoding the customer id + gym tenant reference
/// (see [EnrollmentQrPayload]). A staff member scans it at a biometric
/// access device to enroll the customer's credentials.
class EnrollmentQrPage extends ConsumerWidget {
  const EnrollmentQrPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(authProvider).user;

    return Scaffold(
      appBar: AppBar(title: const Text('Enrollment QR')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: user == null || user.tenantId == null
                ? const _UnavailableCard()
                : _EnrollmentQrCard(
                    payload: EnrollmentQrPayload(
                      customerId: user.id,
                      tenantId: user.tenantId!,
                    ),
                    customerName: user.fullName,
                    gymName: user.tenantName,
                  ),
          ),
        ),
      ),
    );
  }
}

/// Card holding the QR code and customer/gym details.
class _EnrollmentQrCard extends StatelessWidget {
  final EnrollmentQrPayload payload;
  final String customerName;
  final String? gymName;

  const _EnrollmentQrCard({
    required this.payload,
    required this.customerName,
    this.gymName,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.qr_code, color: AppTheme.primary, size: 32),
          const SizedBox(height: 8),
          Text(
            'Enrollment QR',
            style: Theme.of(context)
                .textTheme
                .titleLarge
                ?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text(
            'Show this code to gym staff to enroll your biometric access at the door device.',
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
          ),
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppTheme.divider),
            ),
            child: QrImageView(
              data: payload.encode(),
              version: QrVersions.auto,
              size: 260,
              gapless: true,
              backgroundColor: Colors.white,
              semanticsLabel:
                  'Enrollment QR: customer ${payload.customerId}, gym ${payload.tenantId}',
              eyeStyle: const QrEyeStyle(
                eyeShape: QrEyeShape.square,
                color: AppTheme.textPrimary,
              ),
              dataModuleStyle: const QrDataModuleStyle(
                dataModuleShape: QrDataModuleShape.square,
                color: AppTheme.textPrimary,
              ),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            customerName,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 4),
          Text(
            gymName ?? 'Gym ID: ${payload.tenantId}',
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
          ),
          const SizedBox(height: 4),
          Text(
            'Customer ID: ${payload.customerId}',
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
          ),
        ],
      ),
    );
  }
}

/// Fallback shown when the customer or tenant reference is unavailable.
class _UnavailableCard extends StatelessWidget {
  const _UnavailableCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.cloud_off, size: 48, color: AppTheme.textSecondary),
          const SizedBox(height: 16),
          Text(
            'QR unavailable',
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          const Text(
            'We could not load your gym profile. Please log in again.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 13),
          ),
        ],
      ),
    );
  }
}
