/// A dial-code entry for the phone-input country selector (issue #69).
class CountryCode {
  const CountryCode({
    required this.code,
    required this.name,
    required this.dialCode,
    required this.minLength,
    required this.maxLength,
  });

  /// ISO 3166-1 alpha-2 code, e.g. `IN`.
  final String code;

  /// English display name, e.g. `India`.
  final String name;

  /// Dial code digits without the leading `+`, e.g. `91`.
  final String dialCode;

  /// Pragmatic national-number length range (digits, excluding the dial
  /// code). Exact where the numbering plan is effectively fixed (India 10,
  /// US 10); a range where it is not (UK 7–10).
  final int minLength;
  final int maxLength;

  /// Flag emoji, derived from the ISO code — no image assets needed.
  String get flag => code.toUpperCase().codeUnits
      .map((c) => String.fromCharCode(0x1F1E6 + c - 0x41))
      .join();

  /// Display form with the plus, e.g. `+91`.
  String get displayDialCode => '+$dialCode';

  /// Input hint for the national number, e.g. `10-digit number`.
  String get numberHint => minLength == maxLength
      ? '$minLength-digit number'
      : '$minLength–$maxLength digit number';
}

/// The supported dial codes. Compact on purpose: the gyms' member base is
/// India-first with a long tail of diaspora countries, not a full ITU dump.
class CountryCodes {
  CountryCodes._();

  /// The default selection — India (+91). The app was India-only before
  /// #69; every existing member lands here unchanged.
  static const CountryCode defaultCode = CountryCode(
    code: 'IN',
    name: 'India',
    dialCode: '91',
    minLength: 10,
    maxLength: 10,
  );

  static const List<CountryCode> all = [
    defaultCode,
    // Gulf (large member diaspora).
    CountryCode(code: 'AE', name: 'United Arab Emirates', dialCode: '971', minLength: 7, maxLength: 9),
    CountryCode(code: 'SA', name: 'Saudi Arabia', dialCode: '966', minLength: 9, maxLength: 9),
    CountryCode(code: 'QA', name: 'Qatar', dialCode: '974', minLength: 8, maxLength: 8),
    CountryCode(code: 'KW', name: 'Kuwait', dialCode: '965', minLength: 8, maxLength: 8),
    CountryCode(code: 'OM', name: 'Oman', dialCode: '968', minLength: 8, maxLength: 8),
    CountryCode(code: 'BH', name: 'Bahrain', dialCode: '973', minLength: 8, maxLength: 8),
    // Anglosphere + Europe.
    CountryCode(code: 'GB', name: 'United Kingdom', dialCode: '44', minLength: 7, maxLength: 10),
    CountryCode(code: 'US', name: 'United States', dialCode: '1', minLength: 10, maxLength: 10),
    CountryCode(code: 'CA', name: 'Canada', dialCode: '1', minLength: 10, maxLength: 10),
    CountryCode(code: 'AU', name: 'Australia', dialCode: '61', minLength: 9, maxLength: 9),
    CountryCode(code: 'NZ', name: 'New Zealand', dialCode: '64', minLength: 7, maxLength: 10),
    CountryCode(code: 'DE', name: 'Germany', dialCode: '49', minLength: 7, maxLength: 11),
    CountryCode(code: 'FR', name: 'France', dialCode: '33', minLength: 9, maxLength: 9),
    CountryCode(code: 'IT', name: 'Italy', dialCode: '39', minLength: 9, maxLength: 11),
    CountryCode(code: 'ES', name: 'Spain', dialCode: '34', minLength: 9, maxLength: 9),
    CountryCode(code: 'NL', name: 'Netherlands', dialCode: '31', minLength: 9, maxLength: 9),
    CountryCode(code: 'IE', name: 'Ireland', dialCode: '353', minLength: 7, maxLength: 9),
    CountryCode(code: 'CH', name: 'Switzerland', dialCode: '41', minLength: 9, maxLength: 9),
    CountryCode(code: 'PT', name: 'Portugal', dialCode: '351', minLength: 9, maxLength: 9),
    // South + Southeast Asia.
    CountryCode(code: 'SG', name: 'Singapore', dialCode: '65', minLength: 8, maxLength: 8),
    CountryCode(code: 'MY', name: 'Malaysia', dialCode: '60', minLength: 9, maxLength: 10),
    CountryCode(code: 'LK', name: 'Sri Lanka', dialCode: '94', minLength: 9, maxLength: 9),
    CountryCode(code: 'BD', name: 'Bangladesh', dialCode: '880', minLength: 10, maxLength: 10),
    CountryCode(code: 'PK', name: 'Pakistan', dialCode: '92', minLength: 10, maxLength: 10),
    CountryCode(code: 'NP', name: 'Nepal', dialCode: '977', minLength: 10, maxLength: 10),
    CountryCode(code: 'PH', name: 'Philippines', dialCode: '63', minLength: 10, maxLength: 10),
    CountryCode(code: 'ID', name: 'Indonesia', dialCode: '62', minLength: 9, maxLength: 12),
    CountryCode(code: 'TH', name: 'Thailand', dialCode: '66', minLength: 8, maxLength: 9),
    // East Asia.
    CountryCode(code: 'CN', name: 'China', dialCode: '86', minLength: 11, maxLength: 11),
    CountryCode(code: 'JP', name: 'Japan', dialCode: '81', minLength: 9, maxLength: 10),
    CountryCode(code: 'KR', name: 'South Korea', dialCode: '82', minLength: 9, maxLength: 10),
    // Africa + Americas.
    CountryCode(code: 'ZA', name: 'South Africa', dialCode: '27', minLength: 9, maxLength: 9),
    CountryCode(code: 'NG', name: 'Nigeria', dialCode: '234', minLength: 8, maxLength: 10),
    CountryCode(code: 'KE', name: 'Kenya', dialCode: '254', minLength: 9, maxLength: 9),
    CountryCode(code: 'BR', name: 'Brazil', dialCode: '55', minLength: 10, maxLength: 11),
    CountryCode(code: 'MX', name: 'Mexico', dialCode: '52', minLength: 10, maxLength: 10),
  ];

  /// Looks a country up by ISO code; case-insensitive, null-safe.
  static CountryCode? findByIso(String? code) {
    if (code == null || code.isEmpty) return null;
    final upper = code.toUpperCase();
    for (final country in all) {
      if (country.code == upper) return country;
    }
    return null;
  }
}
