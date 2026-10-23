import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/preferences/dial_code_providers.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/utils/country_code.dart';
import '../../../../core/utils/phone_validator.dart';
import '../providers/auth_notifier.dart';
import '../providers/dial_code_provider.dart';

/// Phone number input screen — first step of OTP auth flow.
///
/// The dial code is picked from the attached selector (default +91 India,
/// issue #69); the field takes the national number. The submitted payload
/// is normalized to `+<dial><national>` exactly as before.
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

  CountryCode get _country => ref.read(selectedCountryProvider);

  void _selectCountry(CountryCode country) {
    ref.read(selectedCountryProvider.notifier).state = country;
    ref.read(dialCodeStoreOrNull)?.save(country);
    setState(() {});
    // Re-run validation: a number too short for the old dial code may be
    // valid for the new one (e.g. 501234567 is 8 digits — invalid for
    // India, valid for the UAE). The field's validator reads the provider
    // live, so this sees the new dial code even before the rebuild.
    if (_phoneController.text.isNotEmpty) _formKey.currentState?.validate();
  }

  Future<void> _openCountryPicker() async {
    final selected = await showModalBottomSheet<CountryCode>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: SizedBox(
          height: MediaQuery.of(sheetContext).size.height * 0.6,
          child: ListView.builder(
            itemCount: CountryCodes.all.length,
            itemBuilder: (context, index) {
              final country = CountryCodes.all[index];
              return ListTile(
                key: ValueKey('country_${country.code}'),
                leading: Text(country.flag, style: const TextStyle(fontSize: 24)),
                title: Text(country.name),
                subtitle: Text(country.numberHint),
                trailing: Text(
                  country.displayDialCode,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                onTap: () => Navigator.of(sheetContext).pop(country),
              );
            },
          ),
        ),
      ),
    );
    if (selected != null) _selectCountry(selected);
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    final phone = PhoneValidator.normalize(_phoneController.text, _country);
    final success = await ref.read(authProvider.notifier).requestOtp(phone);

    if (success && mounted) {
      context.go('/otp', extra: phone);
    }
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);
    final country = ref.watch(selectedCountryProvider);

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
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: AppTheme.textSecondary,
                      ),
                ),

                const SizedBox(height: 32),

                // Phone input with dial-code selector
                TextFormField(
                  controller: _phoneController,
                  keyboardType: TextInputType.phone,
                  autofillHints: const [AutofillHints.telephoneNumberNational],
                  textInputAction: TextInputAction.done,
                  decoration: InputDecoration(
                    labelText: 'Phone Number',
                    hintText: country.numberHint,
                    prefixIcon: _DialCodeChip(
                      country: country,
                      onTap: _openCountryPicker,
                    ),
                  ),
                  // Reads the provider (not the build-captured value) so a
                  // dial-code switch revalidates against the new country.
                  validator: (value) =>
                      PhoneValidator.validateNational(value, _country),
                  onFieldSubmitted: (_) => _submit(),
                ),

                // Error message
                if (authState.errorMessage != null) ...[
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.error.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.error_outline, color: AppTheme.error, size: 20),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            authState.errorMessage!,
                            style: TextStyle(color: AppTheme.error, fontSize: 13),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],

                const SizedBox(height: 32),

                // Submit button
                ElevatedButton(
                  onPressed: authState.isLoading ? null : _submit,
                  child: authState.isLoading
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Text('Send OTP'),
                ),

                const SizedBox(height: 12),

                // Members who installed from a raw Play search have no invite
                // link — they can type the gym code instead (FBOS-011 §7.1).
                TextButton.icon(
                  onPressed: () => context.push('/gym-code'),
                  icon: const Icon(Icons.storefront_outlined, size: 18),
                  label: const Text("I have a gym code"),
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

/// The tappable `🇮🇳 +91 ▾` chip inside the phone field — opens the
/// country picker.
class _DialCodeChip extends StatelessWidget {
  const _DialCodeChip({required this.country, required this.onTap});

  final CountryCode country;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      key: const Key('dial_code_chip'),
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(country.flag, style: const TextStyle(fontSize: 20)),
            const SizedBox(width: 6),
            Text(
              country.displayDialCode,
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
            ),
            const Icon(Icons.keyboard_arrow_down, size: 20),
          ],
        ),
      ),
    );
  }
}
