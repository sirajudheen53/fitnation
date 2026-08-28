/// Customer profile information.
class CustomerProfile {
  final int id;
  final String? name;
  final String? firstName;
  final String? lastName;
  final String? email;
  final String? phone;
  final DateTime? dateOfBirth;
  final String? gender;
  final String? emergencyContact;
  final String? emergencyPhone;
  final String? address;
  final String? addressStreet;
  final String? addressCity;
  final String? addressState;
  final String? addressPostalCode;
  final String? avatarUrl;
  final String? status;
  final String? notes;
  final bool isActive;

  const CustomerProfile({
    required this.id,
    this.name,
    this.firstName,
    this.lastName,
    this.email,
    this.phone,
    this.dateOfBirth,
    this.gender,
    this.emergencyContact,
    this.emergencyPhone,
    this.address,
    this.addressStreet,
    this.addressCity,
    this.addressState,
    this.addressPostalCode,
    this.avatarUrl,
    this.status,
    this.notes,
    this.isActive = true,
  });

  factory CustomerProfile.fromJson(Map<String, dynamic> json) {
    return CustomerProfile(
      id: json['id'] as int,
      name: json['name'] as String?,
      firstName: json['first_name'] as String?,
      lastName: json['last_name'] as String?,
      email: json['email'] as String?,
      phone: json['phone'] as String?,
      dateOfBirth: json['date_of_birth'] != null
          ? DateTime.tryParse(json['date_of_birth'].toString())
          : null,
      gender: json['gender'] as String?,
      emergencyContact: json['emergency_contact_name'] as String? ??
          json['emergency_contact'] as String?,
      emergencyPhone: json['emergency_contact_phone'] as String? ??
          json['emergency_phone'] as String?,
      address: json['address'] as String?,
      addressStreet: json['address_street'] as String?,
      addressCity: json['address_city'] as String?,
      addressState: json['address_state'] as String?,
      addressPostalCode: json['address_postal_code'] as String?,
      avatarUrl: json['avatar_url'] as String? ?? json['profile_photo'] as String?,
      status: json['status'] as String?,
      notes: json['notes'] as String?,
      isActive: (json['is_active'] as bool?) ?? true,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        if (name != null) 'name': name,
        if (firstName != null) 'first_name': firstName,
        if (lastName != null) 'last_name': lastName,
        if (email != null) 'email': email,
        if (phone != null) 'phone': phone,
        if (dateOfBirth != null) 'date_of_birth': dateOfBirth!.toIso8601String(),
        if (gender != null) 'gender': gender,
        if (emergencyContact != null) 'emergency_contact_name': emergencyContact,
        if (emergencyPhone != null) 'emergency_contact_phone': emergencyPhone,
        if (address != null) 'address': address,
        if (addressStreet != null) 'address_street': addressStreet,
        if (addressCity != null) 'address_city': addressCity,
        if (addressState != null) 'address_state': addressState,
        if (addressPostalCode != null) 'address_postal_code': addressPostalCode,
        if (avatarUrl != null) 'avatar_url': avatarUrl,
        if (status != null) 'status': status,
        if (notes != null) 'notes': notes,
        'is_active': isActive,
      };

  /// Full display name.
  String get fullName {
    if (name != null && name!.isNotEmpty) return name!;
    final parts = [firstName, lastName].where((p) => p != null && p.isNotEmpty);
    if (parts.isEmpty) return email ?? 'Customer';
    return parts.join(' ');
  }

  /// The full address, joining the individual address components.
  String? get fullAddress {
    final parts = [
      addressStreet,
      addressCity,
      addressState,
      addressPostalCode,
    ].where((p) => p != null && p.isNotEmpty).toList();
    if (parts.isEmpty) return address;
    return parts.join(', ');
  }
}

/// Health profile for a customer.
class HealthProfile {
  final int id;
  final double? height;
  final double? weight;
  final double? bmi;
  final String? bloodGroup;
  final String? medicalConditions;
  final String? allergies;
  final String? medications;
  final String? activityLevel;
  final String? injuries;
  final String? dietaryRestrictions;

  const HealthProfile({
    required this.id,
    this.height,
    this.weight,
    this.bmi,
    this.bloodGroup,
    this.medicalConditions,
    this.allergies,
    this.medications,
    this.activityLevel,
    this.injuries,
    this.dietaryRestrictions,
  });

  factory HealthProfile.fromJson(Map<String, dynamic> json) {
    return HealthProfile(
      id: json['id'] as int,
      height: (json['height_cm'] as num?)?.toDouble() ??
          (json['height'] as num?)?.toDouble(),
      weight: (json['weight_kg'] as num?)?.toDouble() ??
          (json['weight'] as num?)?.toDouble(),
      bmi: (json['bmi'] as num?)?.toDouble(),
      bloodGroup: json['blood_group'] as String?,
      medicalConditions: _stringify(json['medical_conditions']),
      allergies: _stringify(json['allergies']),
      medications: _stringify(json['medications']),
      activityLevel: json['activity_level'] as String?,
      injuries: json['injuries'] as String?,
      dietaryRestrictions: _stringify(json['dietary_restrictions']),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        if (height != null) 'height_cm': height,
        if (weight != null) 'weight_kg': weight,
        if (bmi != null) 'bmi': bmi,
        if (bloodGroup != null) 'blood_group': bloodGroup,
        if (medicalConditions != null) 'medical_conditions': medicalConditions,
        if (allergies != null) 'allergies': allergies,
        if (medications != null) 'medications': medications,
        if (activityLevel != null) 'activity_level': activityLevel,
        if (injuries != null) 'injuries': injuries,
        if (dietaryRestrictions != null) 'dietary_restrictions': dietaryRestrictions,
      };

  /// Converts a JSON list or string value into a comma-joined string.
  static String? _stringify(dynamic value) {
    if (value == null) return null;
    if (value is String) return value.isEmpty ? null : value;
    if (value is List) {
      final items = value.map((e) => e.toString()).where((e) => e.isNotEmpty);
      if (items.isEmpty) return null;
      return items.join(', ');
    }
    return value.toString();
  }
}

/// Membership information for a customer.
class Membership {
  final int id;
  final String? planName;
  final String? status;
  final DateTime? startDate;
  final DateTime? endDate;
  final double? price;
  final String? branchName;

  const Membership({
    required this.id,
    this.planName,
    this.status,
    this.startDate,
    this.endDate,
    this.price,
    this.branchName,
  });

  factory Membership.fromJson(Map<String, dynamic> json) {
    return Membership(
      id: json['id'] as int,
      planName: json['plan_name'] as String?,
      status: json['status'] as String?,
      startDate: json['start_date'] != null
          ? DateTime.tryParse(json['start_date'].toString())
          : null,
      endDate: json['end_date'] != null
          ? DateTime.tryParse(json['end_date'].toString())
          : null,
      price: (json['price'] as num?)?.toDouble(),
      branchName: json['branch_name'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        if (planName != null) 'plan_name': planName,
        if (status != null) 'status': status,
        if (startDate != null) 'start_date': startDate!.toIso8601String(),
        if (endDate != null) 'end_date': endDate!.toIso8601String(),
        if (price != null) 'price': price,
        if (branchName != null) 'branch_name': branchName,
      };

  /// Whether the membership is currently active.
  bool get isActive {
    final statusLower = status?.toLowerCase() ?? '';
    if (statusLower == 'active' || statusLower == 'active_membership') return true;
    if (endDate == null) return false;
    return endDate!.isAfter(DateTime.now());
  }
}
