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
  /// Override for real devices / other environments with:
  /// `flutter run --dart-define=FBOS_API_BASE=https://<real-server>`
  /// Default keeps the Android emulator loopback so `flutter run` works as-is.
  static const String apiBaseUrl = String.fromEnvironment(
    'FBOS_API_BASE',
    defaultValue: 'http://10.0.2.2:8000', // Android emulator -> host localhost
  );
  static const String apiPrefix = '/api/v1';

  /// API endpoints.
  static const String otpRequestEndpoint = '/auth/otp/request/';
  static const String otpVerifyEndpoint = '/auth/otp/verify/';
  static const String firebaseAuthEndpoint = '/auth/firebase/';
  static const String logoutEndpoint = '/auth/logout/';
  static const String meEndpoint = '/auth/me/';

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
