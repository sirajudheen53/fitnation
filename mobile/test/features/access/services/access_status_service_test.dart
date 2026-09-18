import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/access/services/access_status_service.dart';
import 'package:fitnation_app/features/profile/data/models/customer_profile.dart';

void main() {
  // Fixed "now" so day calculations are deterministic.
  final now = DateTime(2026, 9, 18, 10, 30);

  group('AccessStatusService.evaluate', () {
    test('null end date maps to unknown and does not notify', () {
      final info = AccessStatusService.evaluate(null, now: now);

      expect(info.status, AccessStatus.unknown);
      expect(info.shouldNotify, isFalse);
      expect(info.daysRemaining, isNull);
    });

    test('end date in the past maps to expired', () {
      final info = AccessStatusService.evaluate(
        DateTime(2026, 9, 15),
        now: now,
      );

      expect(info.status, AccessStatus.expired);
      expect(info.message, 'Your gym access has expired');
      expect(info.daysRemaining, -3);
      expect(info.shouldNotify, isTrue);
    });

    test('end date today maps to expiring soon with expires-today message', () {
      final info = AccessStatusService.evaluate(
        DateTime(2026, 9, 18, 23, 59),
        now: now,
      );

      expect(info.status, AccessStatus.expiringSoon);
      expect(info.message, 'Your access expires today');
      expect(info.daysRemaining, 0);
      expect(info.shouldNotify, isTrue);
    });

    test('one day remaining uses the tomorrow wording', () {
      final info = AccessStatusService.evaluate(
        DateTime(2026, 9, 19),
        now: now,
      );

      expect(info.status, AccessStatus.expiringSoon);
      expect(info.message, 'Your access expires tomorrow');
      expect(info.daysRemaining, 1);
    });

    test('three days remaining uses the in-N-days wording', () {
      final info = AccessStatusService.evaluate(
        DateTime(2026, 9, 21),
        now: now,
      );

      expect(info.status, AccessStatus.expiringSoon);
      expect(info.message, 'Your access expires in 3 days');
      expect(info.daysRemaining, 3);
      expect(info.title, 'Access expiring soon');
    });

    test('threshold day still counts as expiring soon', () {
      final info = AccessStatusService.evaluate(
        DateTime(2026, 9, 25),
        now: now,
      );

      expect(AccessStatusService.expiringSoonThresholdDays, 7);
      expect(info.daysRemaining, 7);
      expect(info.status, AccessStatus.expiringSoon);
    });

    test('beyond the threshold maps to active and does not notify', () {
      final info = AccessStatusService.evaluate(
        DateTime(2026, 10, 18),
        now: now,
      );

      expect(info.status, AccessStatus.active);
      expect(info.message, 'Your gym access is active');
      expect(info.daysRemaining, 30);
      expect(info.shouldNotify, isFalse);
    });

    test('day counting is calendar-based, not a 24h difference', () {
      // 23:00 now vs 08:00 two calendar days later is still "2 days",
      // even though the raw difference is under 48 hours.
      final info = AccessStatusService.evaluate(
        DateTime(2026, 9, 20, 8),
        now: DateTime(2026, 9, 18, 23),
      );

      expect(info.daysRemaining, 2);
      expect(info.message, 'Your access expires in 2 days');
    });
  });

  group('AccessStatusService.evaluateMemberships', () {
    Membership membership(DateTime? endDate) => Membership(
          id: 1,
          endDate: endDate,
        );

    test('empty list maps to unknown', () {
      final info = AccessStatusService.evaluateMemberships(const [], now: now);

      expect(info.status, AccessStatus.unknown);
    });

    test('memberships without end dates map to unknown', () {
      final info = AccessStatusService.evaluateMemberships(
        [membership(null)],
        now: now,
      );

      expect(info.status, AccessStatus.unknown);
    });

    test('uses the latest end date as the access window', () {
      final info = AccessStatusService.evaluateMemberships(
        [
          membership(DateTime(2026, 8, 1)), // older, expired term
          membership(DateTime(2026, 9, 21)), // current term
        ],
        now: now,
      );

      expect(info.status, AccessStatus.expiringSoon);
      expect(info.daysRemaining, 3);
    });

    test('all memberships expired maps to expired', () {
      final info = AccessStatusService.evaluateMemberships(
        [
          membership(DateTime(2026, 9, 1)),
          membership(DateTime(2026, 9, 10)),
        ],
        now: now,
      );

      expect(info.status, AccessStatus.expired);
      expect(info.message, 'Your gym access has expired');
    });
  });
}
