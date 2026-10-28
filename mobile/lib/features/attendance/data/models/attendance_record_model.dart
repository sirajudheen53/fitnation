/// One gym check-in record for the logged-in customer.
///
/// Mirrors the payload of GET /api/v1/attendance/attendance/ (issue #95),
/// which returns the customer's own records, most recent first, when the
/// caller is a customer.
class AttendanceRecordModel {
  final int id;
  final DateTime checkInTime;

  /// Null while the member is still in the gym.
  final DateTime? checkOutTime;

  /// True when the backend closed the record automatically (open > 2h).
  final bool checkOutIsAuto;
  final String? status;
  final String? method;
  final String? branchName;

  const AttendanceRecordModel({
    required this.id,
    required this.checkInTime,
    this.checkOutTime,
    this.checkOutIsAuto = false,
    this.status,
    this.method,
    this.branchName,
  });

  factory AttendanceRecordModel.fromJson(Map<String, dynamic> json) {
    return AttendanceRecordModel(
      id: json['id'] as int,
      checkInTime: DateTime.parse(json['check_in_time'] as String),
      checkOutTime: json['check_out_time'] == null
          ? null
          : DateTime.parse(json['check_out_time'] as String),
      checkOutIsAuto: (json['check_out_is_auto'] as bool?) ?? false,
      status: json['status'] as String?,
      method: json['method'] as String?,
      branchName: json['branch_name'] as String?,
    );
  }

  @override
  String toString() =>
      'AttendanceRecordModel(id: $id, in: $checkInTime, out: $checkOutTime)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is AttendanceRecordModel && other.id == id;

  @override
  int get hashCode => id.hashCode;
}

/// Derived check-in state shown on the home card (issue #95).
class CheckInSummary {
  /// The open visit — the member is in the gym right now.
  final AttendanceRecordModel? active;

  /// The most recent visit that has a check-out.
  final AttendanceRecordModel? lastCompleted;

  const CheckInSummary({this.active, this.lastCompleted});

  bool get isCheckedIn => active != null;

  /// The record the home card should display, if any.
  AttendanceRecordModel? get latest => active ?? lastCompleted;

  /// Derives the summary from the API's most-recent-first record list.
  ///
  /// Scans instead of only looking at the first row so the derivation stays
  /// correct even if the ordering ever changes.
  static CheckInSummary fromRecords(List<AttendanceRecordModel> records) {
    AttendanceRecordModel? active;
    AttendanceRecordModel? lastCompleted;
    for (final record in records) {
      if (active == null && record.checkOutTime == null) active = record;
      if (lastCompleted == null && record.checkOutTime != null) {
        lastCompleted = record;
      }
      if (active != null && lastCompleted != null) break;
    }
    return CheckInSummary(active: active, lastCompleted: lastCompleted);
  }

  @override
  String toString() =>
      'CheckInSummary(checkedIn: $isCheckedIn, lastCompleted: $lastCompleted)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is CheckInSummary &&
          other.active == active &&
          other.lastCompleted == lastCompleted;

  @override
  int get hashCode => Object.hash(active, lastCompleted);
}
