// Core constants for the FitNation app.

/// Which login backend the app uses.
enum AuthMode {
  /// Firebase phone-OTP login (SMS code verified by Firebase, then the
  /// Firebase ID token is exchanged for a session via POST /auth/firebase/).
  firebase,

  /// Legacy backend OTP login (POST /auth/otp/request/ + /auth/otp/verify/).
  /// Kept as the rollback path — do not delete.
  backendOtp,
}

class AppConstants {
  AppConstants._();

  /// Auth mode. Compile-time switchable:
  /// `flutter run --dart-define=FBOS_USE_FIREBASE_AUTH=false` rolls back to
  /// the backend-OTP flow without a code change.
  static const bool _useFirebaseAuth = bool.fromEnvironment(
    'FBOS_USE_FIREBASE_AUTH',
    defaultValue: true,
  );

  /// Test-only override for [authMode]; null (the default) keeps the
  /// compile-time behaviour. Never set outside test code.
  static AuthMode? debugAuthModeOverride;

  static AuthMode get authMode =>
      debugAuthModeOverride ??
      (_useFirebaseAuth ? AuthMode.firebase : AuthMode.backendOtp);

  /// Base URL for the FBOS API.
  /// Default is the production Cloud Run backend so release builds work on
  /// real devices out of the box.
  /// For local development / Android emulator, override with:
  /// `flutter run --dart-define=FBOS_API_BASE=http://10.0.2.2:8000`
  static const String apiBaseUrl = String.fromEnvironment(
    'FBOS_API_BASE',
    defaultValue:
        'https://fitnation-backend-prod-6qezqfxxla-el.a.run.app', // prod Cloud Run
  );
  static const String apiPrefix = '/api/v1';

  /// API endpoints.
  static const String otpRequestEndpoint = '/auth/otp/request/';
  static const String otpVerifyEndpoint = '/auth/otp/verify/';
  static const String firebaseAuthEndpoint = '/auth/firebase/';
  static const String logoutEndpoint = '/auth/logout/';
  static const String meEndpoint = '/auth/me/';

  /// Plan assignments (issue #94) — the active variant returns the
  /// logged-in customer's own active assignments.
  static const String workoutAssignmentsActiveEndpoint =
      '/workouts/workout-assignments/active/';
  static const String dietAssignmentsActiveEndpoint =
      '/diet-assignments/active/';

  /// Storage keys.
  static const String authTokenKey = 'auth_token';
  static const String userProfileKey = 'user_profile';
  static const String permissionsKey = 'user_permissions';

  /// OTP configuration.
  static const int otpLength = 6;
  static const Duration otpResendCooldown = Duration(seconds: 30);
  static const Duration otpExpiry = Duration(minutes: 5);

  /// Phone validation.
  static const int phoneMinLength = 10;
  static const int phoneMaxLength = 15;

  /// Firebase phone verification timeout (auto-SMS-retrieval window).
  static const Duration phoneVerificationTimeout = Duration(seconds: 60);
}
