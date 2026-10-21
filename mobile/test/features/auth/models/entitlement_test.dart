import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/auth/data/models/entitlement.dart';

void main() {
  group('AppEntitlementStatus.fromString', () {
    test('maps every server status', () {
      expect(
        AppEntitlementStatus.fromString('active'),
        AppEntitlementStatus.active,
      );
      expect(
        AppEntitlementStatus.fromString('grace'),
        AppEntitlementStatus.grace,
      );
      expect(
        AppEntitlementStatus.fromString('expired'),
        AppEntitlementStatus.expired,
      );
      expect(
        AppEntitlementStatus.fromString('none'),
        AppEntitlementStatus.none,
      );
    });

    test('an unknown or missing status degrades to none', () {
      expect(
        AppEntitlementStatus.fromString('something-else'),
        AppEntitlementStatus.none,
      );
      expect(AppEntitlementStatus.fromString(null), AppEntitlementStatus.none);
      expect(AppEntitlementStatus.fromString(''), AppEntitlementStatus.none);
    });
  });

  group('Entitlement.fromJson', () {
    test('parses the full backend payload', () {
      final entitlement = Entitlement.fromJson({
        'status': 'grace',
        'read_only': true,
        'plan_name': 'Monthly Unlimited',
        'end_date': '2026-10-14',
        'grace_end_date': '2026-10-21',
        'gym': {'uuid': 'gym-uuid-1', 'name': 'Hash Fit'},
      });

      expect(entitlement.status, AppEntitlementStatus.grace);
      expect(entitlement.readOnly, isTrue);
      expect(entitlement.planName, 'Monthly Unlimited');
      expect(entitlement.endDate, DateTime(2026, 10, 14));
      expect(entitlement.graceEndDate, DateTime(2026, 10, 21));
      expect(entitlement.gymUuid, 'gym-uuid-1');
      expect(entitlement.gymName, 'Hash Fit');
    });

    test('missing fields degrade safely', () {
      final entitlement = Entitlement.fromJson({});

      expect(entitlement.status, AppEntitlementStatus.none);
      expect(entitlement.readOnly, isFalse);
      expect(entitlement.planName, isNull);
      expect(entitlement.endDate, isNull);
      expect(entitlement.graceEndDate, isNull);
      expect(entitlement.gymUuid, isNull);
      expect(entitlement.gymName, isNull);
    });

    test('an unparseable date degrades to null', () {
      final entitlement = Entitlement.fromJson({
        'status': 'expired',
        'end_date': 'not-a-date',
      });

      expect(entitlement.endDate, isNull);
    });

    test('an empty date string degrades to null', () {
      final entitlement = Entitlement.fromJson({
        'status': 'expired',
        'end_date': '',
      });

      expect(entitlement.endDate, isNull);
    });

    test('a non-map gym degrades to null gym fields', () {
      final entitlement = Entitlement.fromJson({
        'status': 'active',
        'gym': 'not-a-map',
      });

      expect(entitlement.gymUuid, isNull);
      expect(entitlement.gymName, isNull);
    });
  });

  group('entitlement state', () {
    test('active is entitled and does not need the gate', () {
      const entitlement = Entitlement(status: AppEntitlementStatus.active);

      expect(entitlement.isEntitled, isTrue);
      expect(entitlement.requiresGate, isFalse);
      expect(entitlement.isReadOnlyGrace, isFalse);
    });

    test('grace is entitled but read-only', () {
      const entitlement = Entitlement(
        status: AppEntitlementStatus.grace,
        readOnly: true,
      );

      expect(entitlement.isEntitled, isTrue);
      expect(entitlement.requiresGate, isFalse);
      expect(entitlement.isReadOnlyGrace, isTrue);
    });

    test('expired needs the gate', () {
      const entitlement = Entitlement(status: AppEntitlementStatus.expired);

      expect(entitlement.isEntitled, isFalse);
      expect(entitlement.requiresGate, isTrue);
    });

    test('none needs the gate', () {
      const entitlement = Entitlement(status: AppEntitlementStatus.none);

      expect(entitlement.isEntitled, isFalse);
      expect(entitlement.requiresGate, isTrue);
    });
  });

  group('copyWith', () {
    test('replaces the given fields and keeps the rest', () {
      const original = Entitlement(
        status: AppEntitlementStatus.active,
        planName: 'Monthly',
        gymName: 'Hash Fit',
      );

      final updated = original.copyWith(
        status: AppEntitlementStatus.grace,
        readOnly: true,
      );

      expect(updated.status, AppEntitlementStatus.grace);
      expect(updated.readOnly, isTrue);
      expect(updated.planName, 'Monthly');
      expect(updated.gymName, 'Hash Fit');
    });
  });

  group('toJson', () {
    test('round-trips through fromJson', () {
      const original = Entitlement(
        status: AppEntitlementStatus.grace,
        readOnly: true,
        planName: 'Monthly Unlimited',
        endDate: null,
        gymUuid: 'gym-uuid-1',
        gymName: 'Hash Fit',
      );

      final restored = Entitlement.fromJson(original.toJson());

      expect(restored, original);
    });

    test('omits null fields', () {
      const entitlement = Entitlement(status: AppEntitlementStatus.none);

      final json = entitlement.toJson();

      expect(json.containsKey('plan_name'), isFalse);
      expect(json.containsKey('gym'), isFalse);
      expect(json['status'], 'none');
    });
  });

  group('equality', () {
    test('two entitlements with the same fields are equal', () {
      const a = Entitlement(status: AppEntitlementStatus.active, gymName: 'A');
      const b = Entitlement(status: AppEntitlementStatus.active, gymName: 'A');

      expect(a, b);
      expect(a.hashCode, b.hashCode);
    });

    test('a different status makes them unequal', () {
      const a = Entitlement(status: AppEntitlementStatus.active);
      const b = Entitlement(status: AppEntitlementStatus.expired);

      expect(a, isNot(b));
    });
  });
}
