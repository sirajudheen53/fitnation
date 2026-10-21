import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/features/profile/data/models/customer_profile.dart';

void main() {
  group('CustomerProfile.fromJson', () {
    test('parses a full payload', () {
      final profile = CustomerProfile.fromJson({
        'id': 7,
        'name': 'Asha Kumar',
        'first_name': 'Asha',
        'last_name': 'Kumar',
        'email': 'asha@example.com',
        'phone': '+919999000001',
        'date_of_birth': '1995-04-12T00:00:00Z',
        'gender': 'female',
        'emergency_contact_name': 'Venkat',
        'emergency_contact_phone': '+919999000002',
        'address': '18 Rose Street',
        'address_street': '18 Rose Street',
        'address_city': 'Chennai',
        'address_state': 'TN',
        'address_postal_code': '600001',
        'avatar_url': 'https://cdn.example.com/a.png',
        'status': 'active',
        'notes': 'knee injury',
        'is_active': true,
      });

      expect(profile.id, 7);
      expect(profile.name, 'Asha Kumar');
      expect(profile.firstName, 'Asha');
      expect(profile.lastName, 'Kumar');
      expect(profile.email, 'asha@example.com');
      expect(profile.phone, '+919999000001');
      expect(profile.dateOfBirth, DateTime.parse('1995-04-12T00:00:00Z'));
      expect(profile.gender, 'female');
      expect(profile.emergencyContact, 'Venkat');
      expect(profile.emergencyPhone, '+919999000002');
      expect(profile.address, '18 Rose Street');
      expect(profile.addressStreet, '18 Rose Street');
      expect(profile.addressCity, 'Chennai');
      expect(profile.addressState, 'TN');
      expect(profile.addressPostalCode, '600001');
      expect(profile.avatarUrl, 'https://cdn.example.com/a.png');
      expect(profile.status, 'active');
      expect(profile.notes, 'knee injury');
      expect(profile.isActive, isTrue);
    });

    test('accepts the alias keys the server actually sends', () {
      final profile = CustomerProfile.fromJson({
        'id': 8,
        'emergency_contact': 'Mum',
        'emergency_phone': '+919999000003',
        'profile_photo': 'https://cdn.example.com/photo.png',
      });

      expect(profile.emergencyContact, 'Mum');
      expect(profile.emergencyPhone, '+919999000003');
      expect(profile.avatarUrl, 'https://cdn.example.com/photo.png');
    });

    test('is_active defaults to true when the server omits it', () {
      expect(CustomerProfile.fromJson({'id': 1}).isActive, isTrue);
    });
  });

  group('CustomerProfile.toJson', () {
    test('round-trips a fully-populated profile', () {
      final profile = CustomerProfile(
        id: 9,
        name: 'Ravi Menon',
        firstName: 'Ravi',
        lastName: 'Menon',
        email: 'ravi@example.com',
        phone: '+919999000004',
        dateOfBirth: DateTime(1990, 8, 1),
        gender: 'male',
        emergencyContact: 'Sita',
        emergencyPhone: '+919999000005',
        address: '5 Beach Road',
        addressStreet: '5 Beach Road',
        addressCity: 'Kochi',
        addressState: 'KL',
        addressPostalCode: '682001',
        avatarUrl: 'https://cdn.example.com/r.png',
        status: 'active',
        notes: '',
        isActive: true,
      );

      final json = profile.toJson();
      expect(json, CustomerProfile.fromJson(json).toJson());
      final reparsed = CustomerProfile.fromJson(json);
      expect(reparsed.id, profile.id);
      expect(reparsed.name, profile.name);
      expect(reparsed.phone, profile.phone);
      expect(reparsed.dateOfBirth, profile.dateOfBirth);
      expect(reparsed.addressPostalCode, profile.addressPostalCode);
    });

    test('omits null fields', () {
      final json = const CustomerProfile(id: 3).toJson();
      expect(json, {'id': 3, 'is_active': true});
    });
  });

  group('CustomerProfile.fullName', () {
    test('prefers the full name when present', () {
      const profile = CustomerProfile(id: 1, name: 'Ravi Menon', firstName: 'R', lastName: 'M');
      expect(profile.fullName, 'Ravi Menon');
    });

    test('joins first and last name', () {
      const profile = CustomerProfile(id: 1, firstName: 'Ravi', lastName: 'Menon');
      expect(profile.fullName, 'Ravi Menon');
    });

    test('falls back to the email, then Customer', () {
      const withEmail = CustomerProfile(id: 1, email: 'x@example.com');
      expect(withEmail.fullName, 'x@example.com');
      const bare = CustomerProfile(id: 1);
      expect(bare.fullName, 'Customer');
    });
  });

  group('CustomerProfile.fullAddress', () {
    test('joins the components that exist', () {
      const profile = CustomerProfile(id: 1, addressCity: 'Kochi', addressPostalCode: '682001');
      expect(profile.fullAddress, 'Kochi, 682001');
    });

    test('falls back to the legacy single-line address', () {
      const profile = CustomerProfile(id: 1, address: '5 Beach Road');
      expect(profile.fullAddress, '5 Beach Road');
    });

    test('is null when nothing is set', () {
      const profile = CustomerProfile(id: 1);
      expect(profile.fullAddress, isNull);
    });
  });

  group('HealthProfile', () {
    test('parses a full payload with the canonical keys', () {
      final health = HealthProfile.fromJson({
        'id': 4,
        'height_cm': 171.5,
        'weight_kg': 68.2,
        'bmi': 23.2,
        'blood_group': 'O+',
        'medical_conditions': ['Asthma'],
        'allergies': 'Peanuts',
        'medications': 'Inhaler',
        'activity_level': 'moderate',
        'injuries': 'Twisted ankle 2023',
        'dietary_restrictions': ['Veg'],
      });

      expect(health.id, 4);
      expect(health.height, 171.5);
      expect(health.weight, 68.2);
      expect(health.bmi, 23.2);
      expect(health.bloodGroup, 'O+');
      expect(health.medicalConditions, 'Asthma');
      expect(health.allergies, 'Peanuts');
      expect(health.medications, 'Inhaler');
      expect(health.activityLevel, 'moderate');
      expect(health.injuries, 'Twisted ankle 2023');
      expect(health.dietaryRestrictions, 'Veg');
    });

    test('accepts height/weight without the unit suffix', () {
      final health = HealthProfile.fromJson({'id': 1, 'height': 180, 'weight': 75});
      expect(health.height, 180.0);
      expect(health.weight, 75.0);
    });

    test('stringify degrades an empty string and an empty list to null', () {
      expect(HealthProfile.fromJson({'id': 1, 'allergies': ''}).allergies, isNull);
      expect(
        HealthProfile.fromJson({'id': 1, 'allergies': <String>[]}).allergies,
        isNull,
      );
      expect(
        HealthProfile.fromJson({'id': 1, 'allergies': ['A', '', 'B']}).allergies,
        'A, B',
      );
      expect(HealthProfile.fromJson({'id': 1, 'allergies': 42}).allergies, '42');
    });

    test('toJson round-trips and omits nulls', () {
      const health = HealthProfile(id: 2, height: 180.0, bloodGroup: 'AB+');
      final json = health.toJson();
      expect(json.containsKey('weight_kg'), isFalse);
      final reparsed = HealthProfile.fromJson(json);
      expect(reparsed.height, health.height);
      expect(reparsed.bloodGroup, health.bloodGroup);
    });
  });

  group('Membership', () {
    test('parses and round-trips', () {
      final membership = Membership.fromJson({
        'id': 5,
        'plan_name': 'Gold',
        'status': 'active',
        'start_date': '2026-01-01T00:00:00Z',
        'end_date': '2027-01-01T00:00:00Z',
        'price': 12000.0,
        'branch_name': 'Adyar',
      });

      expect(membership.id, 5);
      expect(membership.planName, 'Gold');
      expect(membership.status, 'active');
      expect(membership.startDate, DateTime.parse('2026-01-01T00:00:00Z'));
      expect(membership.endDate, DateTime.parse('2027-01-01T00:00:00Z'));
      expect(membership.price, 12000.0);
      expect(membership.branchName, 'Adyar');

      final json = membership.toJson();
      expect(Membership.fromJson(json).endDate, membership.endDate);
    });

    test('isActive is true for an active-status membership', () {
      const active = Membership(id: 1, status: 'active');
      const casemix = Membership(id: 1, status: 'Active_Membership');
      expect(active.isActive, isTrue);
      expect(casemix.isActive, isTrue);
    });

    test('isActive falls back to the end date for other statuses', () {
      final future = Membership(
        id: 1,
        status: 'upcoming',
        endDate: DateTime.now().add(const Duration(days: 30)),
      );
      final past = Membership(
        id: 1,
        status: 'upcoming',
        endDate: DateTime.now().subtract(const Duration(days: 30)),
      );
      expect(future.isActive, isTrue);
      expect(past.isActive, isFalse);
      expect(const Membership(id: 1, status: 'future-ish').isActive, isFalse);
    });
  });
}