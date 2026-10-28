/// Rupee formatting for API decimal amounts (no intl dependency).
library;

/// Formats an API decimal amount for display.
///
/// "1500.00" → "₹1,500" — paise are kept only when present, thousands are
/// comma-grouped.
String formatRupeeAmount(String decimalAmount) {
  final value = num.tryParse(decimalAmount) ?? 0;
  final isWhole = value == value.truncate();
  final digits = isWhole
      ? value.truncate().toString()
      : value.toStringAsFixed(2);
  final grouped = digits.replaceAll(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    ',',
  );
  return '₹$grouped';
}
