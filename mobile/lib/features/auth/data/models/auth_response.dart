import 'package:json_annotation/json_annotation.dart';
import 'user_model.dart';

part 'auth_response.g.dart';

/// Response from OTP verify endpoint.
@JsonSerializable()
class AuthResponse {
  final String token;
  final UserModel user;
  final List<String> permissions;

  const AuthResponse({
    required this.token,
    required this.user,
    this.permissions = const [],
  });

  factory AuthResponse.fromJson(Map<String, dynamic> json) => _$AuthResponseFromJson(json);

  Map<String, dynamic> toJson() => _$AuthResponseToJson(this);
}