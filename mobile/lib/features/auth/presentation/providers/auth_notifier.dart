import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/user_model.dart';
import '../../domain/repositories/auth_repository.dart';
import 'auth_providers.dart';

/// Represents the authentication state.
@immutable
class AuthState {
  final AuthStatus status;
  final UserModel? user;
  final List<String> permissions;
  final String? errorMessage;
  final bool isLoading;

  const AuthState({
    this.status = AuthStatus.initial,
    this.user,
    this.permissions = const [],
    this.errorMessage,
    this.isLoading = false,
  });

  AuthState copyWith({
    AuthStatus? status,
    UserModel? user,
    List<String>? permissions,
    String? errorMessage,
    bool? isLoading,
  }) {
    return AuthState(
      status: status ?? this.status,
      user: user ?? this.user,
      permissions: permissions ?? this.permissions,
      errorMessage: errorMessage,
      isLoading: isLoading ?? this.isLoading,
    );
  }

  /// Convenience getters.
  bool get isAuthenticated => status == AuthStatus.authenticated;
  bool get isInitial => status == AuthStatus.initial;
  bool get isUnauthenticated => status == AuthStatus.unauthenticated;
}

enum AuthStatus { initial, authenticated, unauthenticated, error }

/// State notifier for authentication.
class AuthNotifier extends StateNotifier<AuthState> {
  final AuthRepository _repository;

  AuthNotifier(this._repository) : super(const AuthState());

  /// Initializes auth state from local storage (called on app start).
  Future<void> init() async {
    state = state.copyWith(isLoading: true);

    final session = _repository.restoreSession();

    if (session.token != null && session.user != null) {
      state = AuthState(
        status: AuthStatus.authenticated,
        user: session.user,
        permissions: session.permissions,
      );
    } else {
      state = const AuthState(status: AuthStatus.unauthenticated);
    }
  }

  /// Requests an OTP for the given phone number.
  Future<bool> requestOtp(String phone) async {
    state = state.copyWith(isLoading: true, errorMessage: null);

    final result = await _repository.requestOtp(phone);

    if (result.error != null) {
      state = state.copyWith(
        status: AuthStatus.unauthenticated,
        isLoading: false,
        errorMessage: result.error!.message,
      );
      return false;
    }

    state = state.copyWith(isLoading: false, errorMessage: null);
    return true;
  }

  /// Verifies the OTP and logs in.
  Future<bool> verifyOtp({required String phone, required String otp}) async {
    state = state.copyWith(isLoading: true, errorMessage: null);

    final result = await _repository.verifyOtp(phone: phone, otp: otp);

    if (result.error != null) {
      state = state.copyWith(
        status: AuthStatus.error,
        isLoading: false,
        errorMessage: result.error!.message,
      );
      return false;
    }

    final response = result.response!;
    state = AuthState(
      status: AuthStatus.authenticated,
      user: response.user,
      permissions: response.permissions,
    );
    return true;
  }

  /// Logs out the user.
  Future<void> logout() async {
    state = state.copyWith(isLoading: true);
    await _repository.logout();
    state = const AuthState(status: AuthStatus.unauthenticated);
  }

  /// Clears any error message.
  void clearError() {
    state = state.copyWith(errorMessage: null, status: AuthStatus.unauthenticated);
  }
}

/// Provides the AuthNotifier.
/// Note: We use a plain provider (not autoDispose) so auth state persists.
final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  final repository = ref.read(authRepositoryProvider);
  return AuthNotifier(repository);
});