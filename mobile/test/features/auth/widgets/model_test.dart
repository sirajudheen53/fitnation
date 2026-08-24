import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/data/models/auth_response.dart';

void main() {
  group('UserModel', () {
    test('fromJson parses all fields correctly', () {
      final json = {
        'id': 42,
        'email': 'raman@example.com',
        'first_name': 'Raman',
        'last_name': 'Nair',
        'role': 'customer',
        'tenant_id': 17,
        'tenant_name': 'Iron Peak Gym',
        'branch_id': 1,
        'branch_name': 'Kochi Main',
        'is_owner': false,
      };

      final user = UserModel.fromJson(json);

      expect(user.id, 42);
      expect(user.email, 'raman@example.com');
      expect(user.firstName, 'Raman');
      expect(user.lastName, 'Nair');
      expect(user.role, 'customer');
      expect(user.tenantId, 17);
      expect(user.tenantName, 'Iron Peak Gym');
      expect(user.branchId, 1);
      expect(user.branchName, 'Kochi Main');
      expect(user.isOwner, false);
    });

    test('fullName returns first + last name', () {
      final user = UserModel(
        id: 1,
        firstName: 'Raman',
        lastName: 'Nair',
        role: 'customer',
      );
      expect(user.fullName, 'Raman Nair');
    });

    test('fullName falls back to email when no name', () {
      final user = UserModel(
        id: 1,
        email: 'test@test.com',
        role: 'customer',
      );
      expect(user.fullName, 'test@test.com');
    });

    test('fullName falls back to "User" when no name or email', () {
      const user = UserModel(id: 1, role: 'customer');
      expect(user.fullName, 'User');
    });

    test('isCustomer returns true for customer role', () {
      const user = UserModel(id: 1, role: 'customer');
      expect(user.isCustomer, true);
    });

    test('isCustomer returns false for trainer role', () {
      const user = UserModel(id: 1, role: 'trainer');
      expect(user.isCustomer, false);
    });

    test('toJson produces correct map', () {
      const user = UserModel(
        id: 1,
        email: 'test@test.com',
        firstName: 'Test',
        lastName: 'User',
        role: 'customer',
      );

      final json = user.toJson();

      expect(json['id'], 1);
      expect(json['email'], 'test@test.com');
      expect(json['first_name'], 'Test');
      expect(json['last_name'], 'User');
      expect(json['role'], 'customer');
    });

    test('copyWith updates only specified fields', () {
      const user = UserModel(id: 1, firstName: 'Old', role: 'customer');
      final updated = user.copyWith(firstName: 'New', role: 'trainer');

      expect(updated.id, 1);
      expect(updated.firstName, 'New');
      expect(updated.role, 'trainer');
    });

    test('equality based on id', () {
      const user1 = UserModel(id: 1, role: 'customer');
      const user2 = UserModel(id: 1, role: 'trainer');
      expect(user1 == user2, true); // same id
      expect(user1.hashCode, user2.hashCode);
    });
  });

  group('AuthResponse', () {
    test('fromJson parses token, user, and permissions', () {
      final json = {
        'token': 'abc123token',
        'user': {
          'id': 1,
          'email': 'test@test.com',
          'role': 'customer',
        },
        'permissions': [
          'memberships.view_membership',
          'payments.view_payment',
        ],
      };

      final response = AuthResponse.fromJson(json);

      expect(response.token, 'abc123token');
      expect(response.user.id, 1);
      expect(response.user.email, 'test@test.com');
      expect(response.permissions.length, 2);
      expect(response.permissions[0], 'memberships.view_membership');
    });

    test('fromJson handles missing permissions', () {
      final json = {
        'token': 'token',
        'user': {'id': 1, 'role': 'customer'},
      };

      final response = AuthResponse.fromJson(json);

      expect(response.token, 'token');
      expect(response.permissions, isEmpty);
    });

    test('toJson produces correct map', () {
      const response = AuthResponse(
        token: 'tkn',
        user: UserModel(id: 1, role: 'customer'),
        permissions: ['workouts.view_workout'],
      );

      final json = response.toJson();

      expect(json['token'], 'tkn');
      expect(json['user']['id'], 1);
      expect(json['permissions'][0], 'workouts.view_workout');
    });

    test('fromJson handles missing token (e.g. /me/ endpoint)', () {
      final json = {
        'user': {'id': 1, 'email': 'test@test.com', 'role': 'customer'},
        'permissions': ['workouts.view_workout'],
      };

      final response = AuthResponse.fromJson(json);

      expect(response.token, isNull);
      expect(response.user.id, 1);
      expect(response.permissions, ['workouts.view_workout']);
    });

    test('toJson omits token when null', () {
      const response = AuthResponse(
        token: null,
        user: UserModel(id: 1, role: 'customer'),
        permissions: [],
      );

      final json = response.toJson();

      expect(json.containsKey('token'), isFalse);
      expect(json['user']['id'], 1);
    });
  });

  group('AppTheme', () {
    testWidgets('theme has correct primary color', (tester) async {
      expect(AppTheme.primary, const Color(0xFF6C13E2));
    });

    test('light theme is a ThemeData', () {
      expect(AppTheme.light, isA<ThemeData>());
    });
  });
}