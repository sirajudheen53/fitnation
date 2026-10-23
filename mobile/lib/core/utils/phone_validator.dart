import 'country_code.dart';

/// Phone number validation against the dial code selected in the picker
/// (issue #69). The field takes the *national* number; the dial code comes
/// from the selector, so validation and the submitted payload are both
/// derived from `+<dial><national>`.
class PhoneValidator {
  PhoneValidator._();

  /// Error message when [value] is not a valid national number for
  /// [country]; null when valid.
  ///
  /// Formatting characters (`+`, spaces, dashes, brackets) are tolerated —
  /// pasting a full international number still works. India keeps its
  /// strict 10-digit rule; other codes get their [CountryCode] length range.
  static String? validateNational(String? value, CountryCode country) {
    if (value == null || value.trim().isEmpty) {
      return 'Please enter your phone number';
    }

    if (!RegExp(r'^[\d\s()+\-]+$').hasMatch(value.trim())) {
      return 'Phone number can only contain digits';
    }

    final digits = toNationalDigits(value, country);
    if (digits.isEmpty) {
      return 'Phone number can only contain digits';
    }

    final range = country.minLength == country.maxLength
        ? '${country.minLength}'
        : '${country.minLength}–${country.maxLength}';
    if (digits.length < country.minLength) {
      return '${country.name} numbers are $range digits';
    }
    if (digits.length > country.maxLength) {
      return '${country.name} numbers are $range digits';
    }

    return null; // valid
  }

  /// Cleans raw input down to bare national digits: drops formatting
  /// characters, a leading trunk zero (`0…`), and a pasted dial-code
  /// prefix. The prefix strip only fires when the full digits are too long
  /// to be a national number *and* the remainder fits — so "+91 98765
  /// 43210" pasted with India selected becomes 9876543210 (no double
  /// country code), while a genuine Indian number like 9198765432 that
  /// happens to start with "91" is left alone.
  static String toNationalDigits(String input, CountryCode country) {
    var digits = input.replaceAll(RegExp(r'\D'), '');
    digits = digits.replaceFirst(RegExp(r'^0+'), '');

    if (digits.startsWith(country.dialCode) &&
        digits.length > country.maxLength &&
        _inRange(digits.substring(country.dialCode.length), country)) {
      digits = digits.substring(country.dialCode.length);
    }
    return digits;
  }

  /// Builds the wire format `+<dial><national>` — the shape the backend
  /// expects, with the country code appearing exactly once.
  static String normalize(String input, CountryCode country) =>
      '+${country.dialCode}${toNationalDigits(input, country)}';

  static bool _inRange(String digits, CountryCode country) =>
      digits.length >= country.minLength && digits.length <= country.maxLength;
}
