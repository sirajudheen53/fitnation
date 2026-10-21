/// Permission helper for checking user permissions in the UI layer.
///
/// The permission set is **server-driven** (FBOS-011 §7.2): the OTP-verify and
/// `/auth/me/` responses carry the member's effective permission list
/// (role set + the entitlement-derived `app.access` code). The static list
/// below is only a safe fallback for the offline/restore path when no server
/// list has been received yet — the server list always wins once present.
class PermissionChecker {
  PermissionChecker._();

  /// Synthetic entitlement code: the member may use the app right now
  /// (FBOS-011 D3). Appended by the server only while entitled.
  static const String appAccess = 'app.access';

  /// Local fallback for the customer role (FBOS-009 subset) — used only when
  /// the server permission list is empty (cold restore before first refresh).
  static const Set<String> fallbackCustomerPermissions = {
    'memberships.view_membership',
    'payments.view_payment',
    'attendance.view_attendance',
    'attendance.log_attendance',
    'workouts.view_workout',
    'diets.view_diet',
  };

  /// The permission list to drive the UI with: the server-provided list when
  /// non-empty, else the safe local fallback.
  static List<String> effectivePermissions(List<String> serverPermissions) {
    if (serverPermissions.isEmpty) {
      return fallbackCustomerPermissions.toList();
    }
    return serverPermissions;
  }

  /// Whether the member holds the app-access entitlement code.
  static bool hasAppAccess(List<String> userPermissions) =>
      userPermissions.contains(appAccess);

  /// Checks if the user has the given permission.
  static bool hasPermission(List<String> userPermissions, String permission) {
    return userPermissions.contains(permission);
  }

  /// Checks if the user has ALL of the given permissions.
  static bool hasAll(List<String> userPermissions, Set<String> permissions) {
    return permissions.every(userPermissions.contains);
  }

  /// Checks if the user has ANY of the given permissions.
  static bool hasAny(List<String> userPermissions, Set<String> permissions) {
    return permissions.any(userPermissions.contains);
  }
}
