import 'package:json_annotation/json_annotation.dart';

part 'user_model.g.dart';

/// User profile returned from the API.
@JsonSerializable()
class UserModel {
  final int id;
  final String? email;
  @JsonKey(name: 'first_name')
  final String? firstName;
  @JsonKey(name: 'last_name')
  final String? lastName;
  final String role;
  @JsonKey(name: 'tenant_id')
  final int? tenantId;
  @JsonKey(name: 'tenant_name')
  final String? tenantName;
  @JsonKey(name: 'branch_id')
  final int? branchId;
  @JsonKey(name: 'branch_name')
  final String? branchName;
  @JsonKey(name: 'is_owner')
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

  factory UserModel.fromJson(Map<String, dynamic> json) => _$UserModelFromJson(json);

  Map<String, dynamic> toJson() => _$UserModelToJson(this);

  /// Full display name.
  String get fullName {
    final parts = [firstName, lastName].where((p) => p != null && p.isNotEmpty);
    if (parts.isEmpty) return email ?? 'User';
    return parts.join(' ');
  }

  /// Whether this user is a customer (mobile app user).
  bool get isCustomer => role == 'customer';

  /// Creates a copy of this model with updated fields.
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