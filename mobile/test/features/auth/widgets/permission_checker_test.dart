import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/auth/services/permission_checker.dart';

void main() {
  group('PermissionChecker', () {
    const customerPerms = [
      'memberships.view_membership',
      'payments.view_payment',
      'attendance.view_attendance',
      'attendance.log_attendance',
      'workouts.view_workout',
      'diets.view_diet',
    ];

    test('hasPermission returns true for existing permission', () {
      expect(
        PermissionChecker.hasPermission(customerPerms, 'workouts.view_workout'),
        true,
      );
    });

    test('hasPermission returns false for missing permission', () {
      expect(
        PermissionChecker.hasPermission(customerPerms, 'users.create_user'),
        false,
      );
    });

    test('hasAll returns true when all permissions present', () {
      expect(
        PermissionChecker.hasAll(
          customerPerms,
          {'workouts.view_workout', 'diets.view_diet'},
        ),
        true,
      );
    });

    test('hasAll returns false when some missing', () {
      expect(
        PermissionChecker.hasAll(
          customerPerms,
          {'workouts.view_workout', 'users.create_user'},
        ),
        false,
      );
    });

    test('hasAny returns true when at least one present', () {
      expect(
        PermissionChecker.hasAny(
          customerPerms,
          {'users.create_user', 'diets.view_diet'},
        ),
        true,
      );
    });

    test('hasAny returns false when none present', () {
      expect(
        PermissionChecker.hasAny(
          customerPerms,
          {'users.create_user', 'reports.view_report'},
        ),
        false,
      );
    });

    test('customer permissions match FBOS-009 spec', () {
      expect(PermissionChecker.fallbackCustomerPermissions, {
        'memberships.view_membership',
        'payments.view_payment',
        'attendance.view_attendance',
        'attendance.log_attendance',
        'workouts.view_workout',
        'diets.view_diet',
      });
    });

    // FBOS-011 §7.2: the permission set is server-driven. The static list is
    // only a fallback for the cold-restore path (no server list yet).
    group('effectivePermissions', () {
      test('uses the server list when it is non-empty', () {
        expect(
          PermissionChecker.effectivePermissions(['app.access', 'diets.view_diet']),
          ['app.access', 'diets.view_diet'],
        );
      });

      test('falls back to the local list when the server list is empty', () {
        expect(
          PermissionChecker.effectivePermissions(const []),
          PermissionChecker.fallbackCustomerPermissions.toList(),
        );
      });
    });

    group('app access code', () {
      test('hasAppAccess is true when the server sent app.access', () {
        expect(
          PermissionChecker.hasAppAccess(['app.access', 'diets.view_diet']),
          true,
        );
      });

      test('hasAppAccess is false without the app.access code', () {
        expect(PermissionChecker.hasAppAccess(customerPerms), false);
      });
    });
  });
}