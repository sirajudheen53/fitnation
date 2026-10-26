import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/utils/phone_validator.dart';
import '../providers/auth_notifier.dart';
import '../providers/auth_providers.dart';

/// Phone number input screen — first step of OTP auth flow.
class PhoneInputScreen extends ConsumerStatefulWidget {
  const PhoneInputScreen({super.key});

  @override
  ConsumerState<PhoneInputScreen> createState() => _PhoneInputScreenState();
}

class _PhoneInputScreenState extends ConsumerState<PhoneInputScreen> {
  final _formKey = GlobalKey<FormState>();
  final _phoneController = TextEditingController();

  @override
  void dispose() {
    _phoneController.dispose();
    super.dispose();
  }

  bool get _isFirebaseMode => AppConstants.authMode == AuthMode.firebase;

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    final phone = PhoneValidator.normalize(_phoneController.text);
    final success = _isFirebaseMode
        ? await ref.read(firebasePhoneAuthProvider.notifier).sendCode(phone)
        : await _requestBackendOtp(phone);

    if (success && mounted) {
      context.go('/otp', extra: phone);
    }
  }

  /// Backend OTP request. Zero-tap: the WhatsApp handshake must be started
  /// before the server dispatches the message — WhatsApp honours zero-tap
  /// only within the handshake window.
  Future<bool> _requestBackendOtp(String phone) async {
    await ref.read(whatsappOtpServiceProvider).startHandshake();
    return ref.read(authProvider.notifier).requestOtp(phone);
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);
    final phoneAuthState = ref.watch(firebasePhoneAuthProvider);

    final isLoading = _isFirebaseMode
        ? phoneAuthState.isLoading
        : authState.isLoading;
    final errorMessage = _isFirebaseMode
        ? (phoneAuthState.errorMessage ?? authState.errorMessage)
        : authState.errorMessage;

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Spacer(flex: 2),

                // Logo / brand
                _buildLogo(),

                const SizedBox(height: 48),

                // Title
                Text(
                  'Welcome to FitNation',
                  style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Enter your phone number to get started',
                  style: Theme.of(context).textTheme.bodyMedium
                      ?.copyWith(color: AppTheme.textSecondary),
                ),

                const SizedBox(height: 32),

                // Phone input
                TextFormField(
                  controller: _phoneController,
                  keyboardType: TextInputType.phone,
                  autofillHints: const [AutofillHints.telephoneNumber],
                  textInputAction: TextInputAction.done,
                  decoration: const InputDecoration(
                    labelText: 'Phone Number',
                    hintText: '+919876543210',
                    prefixIcon: Icon(Icons.phone_outlined),
                  ),
                  validator: PhoneValidator.validate,
                  onFieldSubmitted: (_) => _submit(),
                ),

                // Error message
                if (errorMessage != null) ...[
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.error.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.error_outline,
                          color: AppTheme.error,
                          size: 20,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            errorMessage,
                            style: TextStyle(
                              color: AppTheme.error,
                              fontSize: 13,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],

                const SizedBox(height: 32),

                // Submit button
                ElevatedButton(
                  onPressed: isLoading ? null : _submit,
                  child: isLoading
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Text('Send OTP'),
                ),

                const Spacer(flex: 3),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLogo() {
    return Container(
      width: 80,
      height: 80,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppTheme.primary, AppTheme.primaryLight],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      child: const Icon(Icons.fitness_center, color: Colors.white, size: 40),
    );
  }
}
