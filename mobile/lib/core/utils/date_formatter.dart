/// Human-friendly date formatting for the app (no intl dependency).
library;

const List<String> _monthAbbreviations = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

/// Formats [date] as "01 Oct 2026" (zero-padded day, abbreviated month).
String formatDateShort(DateTime date) {
  final day = date.day.toString().padLeft(2, '0');
  final month = _monthAbbreviations[date.month - 1];
  return '$day $month ${date.year}';
}

/// Formats [date] as "6:04 PM" (12-hour clock, no leading zero on the hour).
String formatTimeShort(DateTime date) {
  final hour12 = date.hour % 12 == 0 ? 12 : date.hour % 12;
  final minute = date.minute.toString().padLeft(2, '0');
  final period = date.hour < 12 ? 'AM' : 'PM';
  return '$hour12:$minute $period';
}
