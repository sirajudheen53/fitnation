/// User profile returned from the API.
class UserModel {
  final int id;
  final String? email;
  final String? firstName;
  final String? lastName;
  final String role;
  final int? tenantId;
  final String? tenantName;
  final int? branchId;
  final String? branchName;
  final bool isOwner;

  const UserModel({
    required this.id,
    this.email,
    this.firstName,
    this.lastName,
    required this.role,
    this.tenantId,
    this.tenantName,
    this.branchId,
    this.branchName,
    this.isOwner = false,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] as int,
      email: json['email'] as String?,
      firstName: json['first_name'] as String?,
      lastName: json['last_name'] as String?,
      role: json['role'] as String,
      tenantId: json['tenant_id'] as int?,
      tenantName: json['tenant_name'] as String?,
      branchId: json['branch_id'] as int?,
      branchName: json['branch_name'] as String?,
      isOwner: (json['is_owner'] as bool?) ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'email': email,
        'first_name': firstName,
        'last_name': lastName,
        'role': role,
        'tenant_id': tenantId,
        'tenant_name': tenantName,
        'branch_id': branchId,
        'branch_name': branchName,
        'is_owner': isOwner,
      };

  /// Full display name.
  String get fullName {
    final parts = [firstName, lastName].where((p) => p != null && p.isNotEmpty);
    if (parts.isEmpty) return email ?? 'User';
    return parts.join(' ');
  }

  /// Whether this user is a customer (mobile app user).
  bool get isCustomer => role == 'customer';

  /// Creates a copy with updated fields.
  UserModel copyWith({
    int? id,
    String? email,
    String? firstName,
    String? lastName,
    String? role,
    int? tenantId,
    String? tenantName,
    int? branchId,
    String? branchName,
    bool? isOwner,
  }) {
    return UserModel(
      id: id ?? this.id,
      email: email ?? this.email,
      firstName: firstName ?? this.firstName,
      lastName: lastName ?? this.lastName,
      role: role ?? this.role,
      tenantId: tenantId ?? this.tenantId,
      tenantName: tenantName ?? this.tenantName,
      branchId: branchId ?? this.branchId,
      branchName: branchName ?? this.branchName,
      isOwner: isOwner ?? this.isOwner,
    );
  }

  @override
  String toString() => 'UserModel(id: $id, name: $fullName, role: $role)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is UserModel && other.id == id;

  @override
  int get hashCode => id.hashCode;
}