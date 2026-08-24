/// An attendance record for a customer.
class AttendanceRecord {
  final int id;
  final int? customerId;
  final DateTime? checkInTime;
  final DateTime? checkOutTime;
  final String? status;
  final String? method;
  final String? branchName;

  const AttendanceRecord({
    required this.id,
    this.customerId,
    this.checkInTime,
    this.checkOutTime,
    this.status,
    this.method,
    this.branchName,
  });

  factory AttendanceRecord.fromJson(Map<String, dynamic> json) {
    return AttendanceRecord(
      id: json['id'] as int,
      customerId: json['customer'] as int? ?? json['customer_id'] as int?,
      checkInTime: json['check_in_time'] != null
          ? DateTime.tryParse(json['check_in_time'].toString())
          : null,
      checkOutTime: json['check_out_time'] != null
          ? DateTime.tryParse(json['check_out_time'].toString())
          : null,
      status: json['status'] as String?,
      method: json['method'] as String?,
      branchName: json['branch_name'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        if (customerId != null) 'customer': customerId,
        if (checkInTime != null) 'check_in_time': checkInTime!.toIso8601String(),
        if (checkOutTime != null) 'check_out_time': checkOutTime!.toIso8601String(),
        if (status != null) 'status': status,
        if (method != null) 'method': method,
        if (branchName != null) 'branch_name': branchName,
      };

  /// Whether this record represents a check-in today.
  bool get isToday {
    final time = checkInTime;
    if (time == null) return false;
    final now = DateTime.now();
    return time.year == now.year &&
        time.month == now.month &&
        time.day == now.day;
  }
}
