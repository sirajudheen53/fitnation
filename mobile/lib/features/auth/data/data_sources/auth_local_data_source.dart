import 'dart:convert';

import 'package:hive/hive.dart';

import '../models/user_model.dart';

/// Local data source for persisting auth state (token + user profile).
class AuthLocalDataSource {
  static const String _boxName = 'auth_box';
  static const String _tokenKey = 'auth_token';
  static const String _userKey = 'user_profile';
  static const String _permissionsKey = 'permissions';

  late Box<dynamic> _box;

  /// Initializes the local data source (call before using).
  Future<void> init() async {
    _box = await Hive.openBox<dynamic>(_boxName);
  }

  /// Saves the auth token.
  Future<void> saveToken(String token) => _box.put(_tokenKey, token);

  /// Gets the stored auth token, or null if not authenticated.
  String? getToken() => _box.get(_tokenKey) as String?;

  /// Saves the user profile.
  Future<void> saveUser(UserModel user) =>
      _box.put(_userKey, jsonEncode(user.toJson()));

  /// Gets the stored user profile, or null.
  UserModel? getUser() {
    final json = _box.get(_userKey) as String?;
    if (json == null) return null;
    return UserModel.fromJson(jsonDecode(json) as Map<String, dynamic>);
  }

  /// Saves the permissions list.
  Future<void> savePermissions(List<String> permissions) =>
      _box.put(_permissionsKey, jsonEncode(permissions));

  /// Gets the stored permissions list.
  List<String> getPermissions() {
    final json = _box.get(_permissionsKey) as String?;
    if (json == null) return [];
    return (jsonDecode(json) as List).cast<String>();
  }

  /// Clears all stored auth data (logout).
  Future<void> clear() async {
    await _box.delete(_tokenKey);
    await _box.delete(_userKey);
    await _box.delete(_permissionsKey);
  }

  /// Whether a token is stored (user is authenticated).
  bool get isAuthenticated => getToken() != null;
}