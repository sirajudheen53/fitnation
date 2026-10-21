import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/anchor/anchor_providers.dart';
import '../../../../core/config/app_config.dart';
import '../../data/models/entitlement.dart';
import '../../data/models/user_model.dart';
import '../../domain/repositories/auth_repository.dart';
import 'auth_providers.dart';

/// Represents the authentication state.
@immutable
class AuthState {
  final AuthStatus status;
  final UserModel? user;
  final List<String> permissions;

  /// App-access entitlement (FBOS-011 §2.3). Null for staff or when the
  /// backend did not send one (legacy) — null never gates.
  final Entitlement? entitlement;

  final String? errorMessage;
  final bool isLoading;

  const AuthState({
    this.status = AuthStatus.initial,
    this.user,
    this.permissions = const [],
    this.entitlement,
    this.errorMessage,
    this.isLoading = false,
  });

  /// Sentinel so [copyWith] can distinguish "leave entitlement" from
  /// "clear entitlement".
  static const Object _noEntitlement = Object();

  AuthState copyWith({
    AuthStatus? status,
    UserModel? user,
    List<String>? permissions,
    Object? entitlement = _noEntitlement,
    String? errorMessage,
    bool? isLoading,
  }) {
    return AuthState(
      status: status ?? this.status,
      user: user ?? this.user,
      permissions: permissions ?? this.permissions,
      entitlement: entitlement == _noEntitlement
          ? this.entitlement
          : entitlement as Entitlement?,
      errorMessage: errorMessage,
      isLoading: isLoading ?? this.isLoading,
    );
  }

  /// Convenience getters.
  bool get isAuthenticated => status == AuthStatus.authenticated;
  bool get isInitial => status == AuthStatus.initial;
  bool get isUnauthenticated => status == AuthStatus.unauthenticated;

  /// The member is gated out (`expired`/`none`) and must see `/gate`.
  bool get isGatedOut {
    final ent = entitlement;
    return ent != null && ent.requiresGate;
  }

  /// Read-only grace: app usable, writes blocked (persistent banner).
  bool get isReadOnlyGrace {
    final ent = entitlement;
    return ent != null && ent.isReadOnlyGrace;
  }
}

enum AuthStatus { initial, authenticated, unauthenticated, error }

/// State notifier for authentication.
class AuthNotifier extends StateNotifier<AuthState> {
  final AuthRepository _repository;

  /// Resolves the effective gym anchor for OTP calls (runtime link anchor
  /// wins over the build-time `--dart-define=GYM_ANCHOR`).
  ///
  /// Null when no anchor store is wired (unit tests) — the backend then
  /// falls back to phone-first auto-pin, which is the right behaviour for a
  /// single-gym deployment.
  final String? Function()? anchorResolver;

  AuthNotifier(this._repository, {this.anchorResolver})
      : super(const AuthState());

  /// The anchor to send with the next OTP request/verify.
  String? get effectiveGymAnchor => anchorResolver?.call();

  /// Initializes auth state from local storage (called on app start).
  Future<void> init() async {
    state = state.copyWith(isLoading: true);

    final session = _repository.restoreSession();

    if (session.token != null && session.user != null) {
      state = AuthState(
        status: AuthStatus.authenticated,
        user: session.user,
        permissions: session.permissions,
        entitlement: session.entitlement,
      );
    } else {
      state = const AuthState(status: AuthStatus.unauthenticated);
    }
  }

  /// Requests an OTP for the given phone number.
  ///
  /// [gymAnchor] defaults to the effective device anchor (runtime link
  /// anchor over build-time define) so the OTP is issued by the right gym.
  Future<bool> requestOtp(String phone, {String? gymAnchor}) async {
    state = state.copyWith(isLoading: true, errorMessage: null);

    final anchor = gymAnchor ?? effectiveGymAnchor;
    final result = await _repository.requestOtp(phone, gymAnchor: anchor);

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
  Future<bool> verifyOtp({
    required String phone,
    required String otp,
    String? gymAnchor,
  }) async {
    state = state.copyWith(isLoading: true, errorMessage: null);

    final anchor = gymAnchor ?? effectiveGymAnchor;
    final result = await _repository.verifyOtp(
      phone: phone,
      otp: otp,
      gymAnchor: anchor,
    );

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
      entitlement: response.entitlement,
    );
    return true;
  }

  /// Refreshes the profile + entitlement from `/auth/me/`.
  Future<bool> refreshProfile() async {
    final result = await _repository.refreshProfile();
    if (result.error != null || result.user == null) {
      return false;
    }
    state = state.copyWith(
      user: result.user,
      permissions: result.permissions,
      entitlement: result.entitlement,
    );
    return true;
  }

  /// Re-checks the live entitlement (`GET /users/auth/entitlement/`).
  ///
  /// Called on app resume (throttled by the caller) and by the gate screen's
  /// refresh button after the member renews at the desk. Server data wins
  /// over the cached value (FBOS-011 §7.2).
  Future<bool> refreshEntitlement() async {
    final result = await _repository.fetchEntitlement();
    final entitlement = result.entitlement;
    if (entitlement == null) {
      // Network failure: keep the cached gate state (fail-safe, not fail-open
      // — a member already gated stays gated until the server says otherwise).
      return false;
    }
    state = state.copyWith(entitlement: entitlement);
    return true;
  }

  /// Applies a server 403 `app_access_*` code from any API response
  /// (FBOS-011 §2.4 — the interceptor feeds this; mid-session revocation
  /// routes to the gate on the very next frame).
  void applyAccessDeniedCode(String? code) {
    if (code == 'app_access_required') {
      state = state.copyWith(
        entitlement: _currentEntitlement(expired: true),
      );
    } else if (code == 'app_access_read_only') {
      state = state.copyWith(
        entitlement: _currentEntitlement(grace: true),
      );
    }
  }

  Entitlement _currentEntitlement({bool expired = false, bool grace = false}) {
    final current = state.entitlement;
    if (current == null) {
      return Entitlement(
        status: expired
            ? AppEntitlementStatus.expired
            : AppEntitlementStatus.grace,
        readOnly: grace,
      );
    }
    if (expired) {
      return current.copyWith(
        status: AppEntitlementStatus.expired,
        readOnly: false,
      );
    }
    return current.copyWith(
      status: AppEntitlementStatus.grace,
      readOnly: true,
    );
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
  return AuthNotifier(
    repository,
    anchorResolver: () => ref.read(anchorStoreOrNullProvider)?.effectiveAnchor(
          buildTimeAnchor: AppEnvironment.gymAnchor,
        ),
  );
});
