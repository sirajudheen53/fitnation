/// Customer profile information.
class CustomerProfile {
  final int id;
  final String? firstName;
  final String? lastName;
  final String? email;
  final String? phone;
  final DateTime? dateOfBirth;
  final String? gender;
  final String? emergencyContact;
  final String? emergencyPhone;
  final String? address;
  final String? avatarUrl;

  const CustomerProfile({
    required this.id,
    this.firstName,
    this.lastName,
    this.email,
    this.phone,
    this.dateOfBirth,
    this.gender,
    this.emergencyContact,
    this.emergencyPhone,
    this.address,
    this.avatarUrl,
  });

  factory CustomerProfile.fromJson(Map<String, dynamic> json) {
    return CustomerProfile(
      id: json['id'] as int,
      firstName: json['first_name'] as String?,
      lastName: json['last_name'] as String?,
      email: json['email'] as String?,
      phone: json['phone'] as String?,
      dateOfBirth: json['date_of_birth'] != null
          ? DateTime.tryParse(json['date_of_birth'].toString())
          : null,
      gender: json['gender'] as String?,
      emergencyContact: json['emergency_contact'] as String?,
      emergencyPhone: json['emergency_phone'] as String?,
      address: json['address'] as String?,
      avatarUrl: json['avatar_url'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        if (firstName != null) 'first_name': firstName,
        if (lastName != null) 'last_name': lastName,
        if (email != null) 'email': email,
        if (phone != null) 'phone': phone,
        if (dateOfBirth != null) 'date_of_birth': dateOfBirth!.toIso8601String(),
        if (gender != null) 'gender': gender,
        if (emergencyContact != null) 'emergency_contact': emergencyContact,
        if (emergencyPhone != null) 'emergency_phone': emergencyPhone,
        if (address != null) 'address': address,
        if (avatarUrl != null) 'avatar_url': avatarUrl,
      };

  /// Full display name.
  String get fullName {
    final parts = [firstName, lastName].where((p) => p != null && p.isNotEmpty);
    if (parts.isEmpty) return email ?? 'Customer';
    return parts.join(' ');
  }
}

/// Health profile for a customer.
class HealthProfile {
  final int id;
  final double? height;
  final double? weight;
  final String? bloodGroup;
  final String? medicalConditions;
  final String? allergies;
  final String? medications;
  final String? activityLevel;

  const HealthProfile({
    required this.id,
    this.height,
    this.weight,
    this.bloodGroup,
    this.medicalConditions,
    this.allergies,
    this.medications,
    this.activityLevel,
  });

  factory HealthProfile.fromJson(Map<String, dynamic> json) {
    return HealthProfile(
      id: json['id'] as int,
      height: (json['height'] as num?)?.toDouble(),
      weight: (json['weight'] as num?)?.toDouble(),
      bloodGroup: json['blood_group'] as String?,
      medicalConditions: json['medical_conditions'] as String?,
      allergies: json['allergies'] as String?,
      medications: json['medications'] as String?,
      activityLevel: json['activity_level'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        if (height != null) 'height': height,
        if (weight != null) 'weight': weight,
        if (bloodGroup != null) 'blood_group': bloodGroup,
        if (medicalConditions != null) 'medical_conditions': medicalConditions,
        if (allergies != null) 'allergies': allergies,
        if (medications != null) 'medications': medications,
        if (activityLevel != null) 'activity_level': activityLevel,
      };
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
