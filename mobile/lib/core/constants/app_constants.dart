/// Core constants for the FitNation app.
import '../config/app_config.dart';

class AppConstants {
  AppConstants._();

  /// Base URL for the FBOS API, resolved per build flavor.
  ///
  /// Delegates to [AppEnvironment.apiBaseUrl] so `--dart-define=SERVER=prod`
  /// (and friends) actually switch hosts; an explicit
  /// `--dart-define=API_BASE_URL=<url>` still wins (FBOS-011 correction #7).
  static String get apiBaseUrl => AppEnvironment.apiBaseUrl;
  static const String apiPrefix = '/api/v1';

  /// API endpoints.
  static const String otpRequestEndpoint = '/users/auth/otp/request/';
  static const String otpVerifyEndpoint = '/users/auth/otp/verify/';
  static const String logoutEndpoint = '/users/auth/logout/';
  static const String meEndpoint = '/users/auth/me/';
  static const String entitlementEndpoint = '/users/auth/entitlement/';
  static const String deviceTokensEndpoint = '/notifications/device-tokens/';


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
  static const String dietAssignmentsEndpoint = '/diet-assignments/';
  static const String dietPlansEndpoint = '/diet-plans/';
  static const String dietMealsEndpoint = '/diet-meals/';

  // Attendance
  static const String attendanceRecordsEndpoint = '/attendance/attendance/';
  static const String attendanceCheckInEndpoint = '/attendance/check-in/';

  // Membership
  static const String membershipsEndpoint = '/memberships/memberships/';

  // Feedback
  static const String feedbackEndpoint = '/feedback/feedback/';

  // AI Coach
  static const String aiCoachChatEndpoint = '/ai/coach/chat/';
  static const String aiCoachConversationsEndpoint = '/ai/coach/conversations/';
  static const String aiCoachMessagesEndpoint = '/ai/coach/conversations/{id}/messages/';

  // Body Analysis
  static const String bodyAnalysisEndpoint = '/ai/body/analyses/';
  static const String bodyAnalysisUploadEndpoint = '/ai/body/analyses/upload/';
  static const String bodyAnalysisProgressEndpoint = '/ai/body/progress/';

  // AI Nutrition
  static const String nutritionMealPlansEndpoint = '/ai/nutrition/meal-plan/';
  static const String nutritionGenerateEndpoint = '/ai/nutrition/meal-plan/generate/';
  static const String nutritionShoppingListEndpoint = '/ai/nutrition/shopping-list/';
  static const String nutritionMacrosEndpoint = '/ai/nutrition/track/';

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