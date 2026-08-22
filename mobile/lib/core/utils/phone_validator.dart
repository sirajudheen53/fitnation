/// Phone number validation utility.
class PhoneValidator {
  PhoneValidator._();

  /// Validates a phone number and returns an error message if invalid.
  /// Expects international format: +<country_code><number>, e.g. +919876543210
  static String? validate(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Please enter your phone number';
    }

    final phone = value.trim();

    if (!phone.startsWith('+')) {
      return 'Include country code (e.g. +91)';
    }

    final digitsOnly = phone.substring(1);
    if (!RegExp(r'^\d+$').hasMatch(digitsOnly)) {
      return 'Phone number can only contain digits';
    }

    if (digitsOnly.length < 10) {
      return 'Phone number is too short';
    }

    if (digitsOnly.length > 15) {
      return 'Phone number is too long';
    }

    return null; // valid
  }

  /// Normalizes a phone number to +<digits> format.
  static String normalize(String phone) {
    final trimmed = phone.trim();
    if (trimmed.startsWith('+')) return trimmed;
    return '+$trimmed';
  }
}