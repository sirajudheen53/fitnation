import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/access/data/models/enrollment_qr_payload.dart';

void main() {
  group('EnrollmentQrPayload', () {
    test('encodes type, customer id, and tenant id as JSON', () {
      const payload = EnrollmentQrPayload(customerId: 42, tenantId: 7);

      expect(
        payload.encode(),
        '{"type":"access_enrollment","customer_id":42,"tenant_id":7}',
      );
    });

    test('decode reverses encode', () {
      const payload = EnrollmentQrPayload(customerId: 42, tenantId: 7);

      final decoded = EnrollmentQrPayload.decode(payload.encode());

      expect(decoded, payload);
      expect(decoded.customerId, 42);
      expect(decoded.tenantId, 7);
    });

    test('equality is by customer id and tenant id', () {
      const a = EnrollmentQrPayload(customerId: 1, tenantId: 2);
      const b = EnrollmentQrPayload(customerId: 1, tenantId: 2);
      const c = EnrollmentQrPayload(customerId: 3, tenantId: 2);

      expect(a, b);
      expect(a.hashCode, b.hashCode);
      expect(a, isNot(c));
    });
  });
}
