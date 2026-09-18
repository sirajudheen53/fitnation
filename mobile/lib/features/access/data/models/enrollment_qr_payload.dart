import 'dart:convert';

/// Payload embedded in the customer's enrollment QR code.
///
/// Encodes the customer id plus the gym tenant reference so staff can scan
/// it at a biometric access device to enroll the customer's credentials
/// (see GET /api/v1/access/credentials/?customer={id}).
class EnrollmentQrPayload {
  static const String typeValue = 'access_enrollment';

  final int customerId;
  final int tenantId;

  const EnrollmentQrPayload({
    required this.customerId,
    required this.tenantId,
  });

  Map<String, dynamic> toJson() => {
        'type': typeValue,
        'customer_id': customerId,
        'tenant_id': tenantId,
      };

  /// JSON string encoded into the QR code.
  String encode() => jsonEncode(toJson());

  factory EnrollmentQrPayload.fromJson(Map<String, dynamic> json) {
    return EnrollmentQrPayload(
      customerId: json['customer_id'] as int,
      tenantId: json['tenant_id'] as int,
    );
  }

  /// Decodes a scanned QR string back into a payload.
  factory EnrollmentQrPayload.decode(String data) {
    return EnrollmentQrPayload.fromJson(
      jsonDecode(data) as Map<String, dynamic>,
    );
  }

  @override
  String toString() =>
      'EnrollmentQrPayload(customerId: $customerId, tenantId: $tenantId)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is EnrollmentQrPayload &&
          other.customerId == customerId &&
          other.tenantId == tenantId;

  @override
  int get hashCode => Object.hash(customerId, tenantId);
}
