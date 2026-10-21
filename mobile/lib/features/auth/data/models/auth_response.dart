import 'entitlement.dart';
import 'user_model.dart';

/// Response from the OTP verify and `/auth/me/` endpoints (FBOS-011 §2.3).
class AuthResponse {
  final String? token;
  final UserModel user;
  final List<String> permissions;

  /// App-access entitlement (absent for staff or legacy backends — null).
  final Entitlement? entitlement;

  const AuthResponse({
    this.token,
    required this.user,
    this.permissions = const [],
    this.entitlement,
  });

  factory AuthResponse.fromJson(Map<String, dynamic> json) {
    final entitlementJson = json['entitlement'];
    return AuthResponse(
      token: json['token'] as String?,
      user: UserModel.fromJson(json['user'] as Map<String, dynamic>),
      permissions: (json['permissions'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      entitlement: entitlementJson is Map<String, dynamic>
          ? Entitlement.fromJson(entitlementJson)
          : null,
    );
  }

  Map<String, dynamic> toJson() => {
        if (token != null) 'token': token,
        'user': user.toJson(),
        'permissions': permissions,
        if (entitlement != null) 'entitlement': entitlement!.toJson(),
      };
}
