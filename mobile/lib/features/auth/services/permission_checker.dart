/// Permission helper for checking user permissions in the UI layer.
class PermissionChecker {
  PermissionChecker._();

  /// Customer permissions (from FBOS-009 spec).
  static const Set<String> customerPermissions = {
    'memberships.view_membership',
    'payments.view_payment',
    'attendance.view_attendance',
    'attendance.log_attendance',
    'workouts.view_workout',
    'diets.view_diet',
  };

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