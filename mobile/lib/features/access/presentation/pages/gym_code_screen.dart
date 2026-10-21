import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/anchor/anchor_providers.dart';
import '../../../../core/errors/failures.dart';
import '../../../../core/theme/app_theme.dart';
import '../providers/gym_code_providers.dart';

/// Manual "enter your gym code" screen (FBOS-011 §7.1).
///
/// Members who install the app from a raw Play search have no invite link
/// and therefore no gym anchor. The gym prints a short code at the front
/// desk; entering it here resolves the gym and pins the device anchor so
/// the OTP is issued by the right gym.
///
/// The endpoint is unauthenticated and throttled, so a wrong code comes back
/// as a 404 — the screen shows a clear message and never crashes.
class GymCodeScreen extends ConsumerStatefulWidget {
  const GymCodeScreen({super.key});

  @override
  ConsumerState<GymCodeScreen> createState() => _GymCodeScreenState();
}

class _GymCodeScreenState extends ConsumerState<GymCodeScreen> {
  final _formKey = GlobalKey<FormState>();
  final _codeController = TextEditingController();

  bool _submitting = false;
  String? _errorMessage;
  String? _successGymName;

  @override
  void dispose() {
    _codeController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });

    final code = _codeController.text.trim().toUpperCase();
    try {
      final gym = await ref
          .read(tenantLookupRemoteDataSourceProvider)
          .lookupByCode(code);

      // Pin the device anchor so the next OTP is issued by this gym.
      final store = ref.read(anchorStoreOrNullProvider);
      if (store != null) {
        await store.save(gymUuid: gym.uuid);
      }

      if (!mounted) return;
      setState(() {
        _submitting = false;
        _successGymName = gym.name;
      });
    } on Failure catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _errorMessage = _messageFor(e);
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _errorMessage = 'Something went wrong. Please try again.';
      });
    }
  }

  /// A 404 (unknown code) is the common case and gets its own copy; the
  /// backend answers every unknown code identically so the app cannot be
  /// used to enumerate gyms.
  String _messageFor(Failure failure) {
    if (failure.statusCode == 404) {
      return 'We could not find that gym code. '
          'Check the code on the screen at the front desk and try again.';
    }
    return failure.message;
  }

  @override
  Widget build(BuildContext context) {
    if (_successGymName != null) {
      return _buildSuccess(context);
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Your gym')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 8),
                  const Icon(Icons.storefront_rounded, size: 56, color: AppTheme.primary),
                  const SizedBox(height: 20),
                  Text(
                    'Enter your gym code',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Your gym has a short code on the screen at the front '
                    'desk. Enter it so we can link your membership to the '
                    'right gym.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: AppTheme.textSecondary, height: 1.5),
                  ),
                  const SizedBox(height: 28),
                  TextFormField(
                    controller: _codeController,
                    textCapitalization: TextCapitalization.characters,
                    textInputAction: TextInputAction.done,
                    maxLength: 12,
                    autocorrect: false,
                    decoration: const InputDecoration(
                      labelText: 'Gym code',
                      hintText: 'e.g. HASHFIT',
                      prefixIcon: Icon(Icons.tag_rounded),
                    ),
                    validator: (value) {
                      final code = (value ?? '').trim();
                      if (code.isEmpty) return 'Enter the code from your gym';
                      if (code.length < 3) return 'That code looks too short';
                      return null;
                    },
                    onFieldSubmitted: (_) => _submit(),
                  ),
                  if (_errorMessage != null) ...[
                    const SizedBox(height: 16),
                    _MessageBox(
                      icon: Icons.error_outline_rounded,
                      color: AppTheme.error,
                      message: _errorMessage!,
                    ),
                  ],
                  const SizedBox(height: 24),
                  ElevatedButton(
                    onPressed: _submitting ? null : _submit,
                    child: _submitting
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Text('Find my gym'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSuccess(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Your gym')),
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.check_circle_rounded,
                      size: 64, color: AppTheme.accent),
                  const SizedBox(height: 20),
                  Text(
                    'You are all set',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Your membership will be linked to $_successGymName. '
                    'Now sign in with your phone number to get started.',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: AppTheme.textSecondary,
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 28),
                  ElevatedButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Continue to sign in'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Inline message box (error / info).
class _MessageBox extends StatelessWidget {
  const _MessageBox({
    required this.icon,
    required this.color,
    required this.message,
  });

  final IconData icon;
  final Color color;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: TextStyle(color: color, fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
}
