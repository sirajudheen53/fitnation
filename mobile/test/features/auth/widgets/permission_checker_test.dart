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
      expect(PermissionChecker.customerPermissions, {
        'memberships.view_membership',
        'payments.view_payment',
        'attendance.view_attendance',
        'attendance.log_attendance',
        'workouts.view_workout',
        'diets.view_diet',
      });
    });
  });
}