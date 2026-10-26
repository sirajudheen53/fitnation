import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/auth/data/models/auth_response.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';

void main() {
  const user = UserModel(
    id: 5,
    email: 'a@b.dev',
    firstName: 'Arjun',
    lastName: 'Nair',
    role: 'customer',
    tenantId: 7,
    tenantName: 'Alpha Gym',
    branchId: 2,
    branchName: 'HSR',
    isOwner: false,
  );

  group('UserModel', () {
    test('parses from API JSON', () {
      final json = user.toJson();
      final parsed = UserModel.fromJson(json);

      expect(parsed.id, 5);
      expect(parsed.email, 'a@b.dev');
      expect(parsed.fullName, 'Arjun Nair');
      expect(parsed.tenantName, 'Alpha Gym');
      expect(parsed.branchName, 'HSR');
      expect(parsed.isCustomer, isTrue);
    });

    test('fullName falls back to email then User', () {
      expect(
        const UserModel(id: 1, role: 'customer', email: 'x@y.dev').fullName,
        'x@y.dev',
      );
      expect(const UserModel(id: 1, role: 'customer').fullName, 'User');
    });

    test('copyWith overrides only given fields', () {
      final updated = user.copyWith(branchName: 'Whitefield');

      expect(updated.branchName, 'Whitefield');
      expect(updated.firstName, 'Arjun');
      expect(updated.tenantId, 7);
    });

    test('equality is by id', () {
      expect(user, const UserModel(id: 5, role: 'other'));
      expect(user, isNot(const UserModel(id: 6, role: 'customer')));
      expect(user.hashCode, user.id.hashCode);
      expect(user.toString(), contains('Arjun Nair'));
    });

    test('isCustomer only for customer role', () {
      expect(user.isCustomer, isTrue);
      expect(const UserModel(id: 1, role: 'trainer').isCustomer, isFalse);
    });
  });

  group('AuthResponse', () {
    test('fromJson parses token, user and permissions', () {
      final response = AuthResponse.fromJson({
        'token': 'tok',
        'user': user.toJson(),
        'permissions': ['workouts.view_workout', 'diets.view_diet'],
      });

      expect(response.token, 'tok');
      expect(response.user.id, 5);
      expect(response.permissions.length, 2);
    });

    test('permissions default to empty when missing', () {
      final response = AuthResponse.fromJson({
        'token': 'tok',
        'user': user.toJson(),
      });

      expect(response.permissions, isEmpty);
    });

    test('toJson roundtrips', () {
      final response = AuthResponse(token: 'tok', user: user);
      final json = response.toJson();

      expect(AuthResponse.fromJson(json).token, 'tok');
    });
  });
}
