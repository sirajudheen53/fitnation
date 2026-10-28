import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/memberships/data/models/membership_model.dart';

void main() {
  Map<String, dynamic> row({int id = 3, String status = 'active'}) => {
        'id': id,
        'customer': 5,
        'customer_id': 5,
        'customer_name': 'Arjun Nair',
        'customer_is_deleted': false,
        'plan': 2,
        'plan_name': 'Monthly',
        'price': 1500.0,
        'start_date': '2026-10-01',
        'end_date': '2026-11-01',
        'status': status,
        'auto_renew': false,
        'created_at': '2026-10-01T09:00:00Z',
        'updated_at': '2026-10-01T09:00:00Z',
      };

  group('MembershipModel', () {
    test('parses an active membership', () {
      final membership = MembershipModel.fromJson(row());

      expect(membership.id, 3);
      expect(membership.plan, 2);
      expect(membership.planName, 'Monthly');
      expect(membership.price, 1500.0);
      expect(membership.startDate, DateTime(2026, 10, 1));
      expect(membership.endDate, DateTime(2026, 11, 1));
      expect(membership.status, 'active');
      expect(membership.isActive, isTrue);
      expect(membership.autoRenew, isFalse);
    });

    test('isActive is false for expired memberships', () {
      expect(MembershipModel.fromJson(row(status: 'expired')).isActive, isFalse);
    });

    test('equality is by id', () {
      final a = MembershipModel.fromJson(row());
      expect(a, MembershipModel.fromJson(row()));
      expect(a, isNot(MembershipModel.fromJson(row(id: 4))));
    });
  });

  group('MembershipModel.pickCurrent', () {
    test('empty list picks nothing', () {
      expect(MembershipModel.pickCurrent(const []), isNull);
    });

    test('prefers the active membership', () {
      final expired = MembershipModel.fromJson(row(id: 1, status: 'expired'));
      final active = MembershipModel.fromJson(row(id: 2));

      expect(MembershipModel.pickCurrent([expired, active]), active);
    });

    test('falls back to the first record when nothing is active', () {
      final first = MembershipModel.fromJson(row(id: 1, status: 'expired'));
      final second = MembershipModel.fromJson(row(id: 2, status: 'expired'));

      expect(MembershipModel.pickCurrent([first, second]), first);
    });
  });
}
