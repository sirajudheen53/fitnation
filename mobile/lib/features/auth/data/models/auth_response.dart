import 'user_model.dart';

/// Response from OTP verify endpoint.
class AuthResponse {
  final String token;
  final UserModel user;
  final List<String> permissions;

  const AuthResponse({
    required this.token,
    required this.user,
    this.permissions = const [],
  });

  factory AuthResponse.fromJson(Map<String, dynamic> json) {
    return AuthResponse(
      token: json['token'] as String,
      user: UserModel.fromJson(json['user'] as Map<String, dynamic>),
      permissions: (json['permissions'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
    );
  }

  Map<String, dynamic> toJson() => {
        'token': token,
        'user': user.toJson(),
        'permissions': permissions,
      };
}