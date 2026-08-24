/// Core constants for the FitNation app.
class AppConstants {
  AppConstants._();

  /// Base URL for the FBOS API.
  /// TODO: Make this configurable per environment (dev/staging/prod).
  static const String apiBaseUrl = 'http://10.0.2.2:8000'; // Android emulator -> host localhost
  static const String apiPrefix = '/api/v1';

  /// API endpoints.
  static const String otpRequestEndpoint = '/auth/otp/request/';
  static const String otpVerifyEndpoint = '/auth/otp/verify/';
  static const String logoutEndpoint = '/auth/logout/';
  static const String meEndpoint = '/auth/me/';

  // Customer
  static const String customerProfileEndpoint = '/customers/customers/';
  static const String customerHealthProfileEndpoint = '/customers/customers/{id}/health-profile/';
  static const String customerFitnessGoalsEndpoint = '/customers/customers/{id}/fitness-goals/';
  static const String customerMeasurementsEndpoint = '/customers/customers/{id}/measurements/';

  // Exercise library
  static const String exercisesEndpoint = '/exercises/exercises/';

  // Workouts
  static const String workoutAssignmentsEndpoint = '/workouts/workout-assignments/';
  static const String workoutPlansEndpoint = '/workouts/workout-plans/';
  static const String workoutLogsEndpoint = '/workouts/workout-logs/';

  // Diet
  static const String dietAssignmentsEndpoint = '/diet/diet-assignments/';
  static const String dietPlansEndpoint = '/diet/diet-plans/';

  // Attendance
  static const String attendanceRecordsEndpoint = '/attendance/attendance-records/';
  static const String attendanceCheckInEndpoint = '/attendance/attendance-records/check-in/';

  // Membership
  static const String membershipsEndpoint = '/memberships/memberships/';

  // Feedback
  static const String feedbackEndpoint = '/feedback/feedback/';

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
}