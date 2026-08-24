import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/attendance/presentation/screens/attendance_history_screen.dart';
import '../features/attendance/presentation/screens/qr_checkin_screen.dart';
import '../features/ai_coach/presentation/screens/ai_chat_screen.dart';
import '../features/ai_nutrition/models/meal_plan.dart';
import '../features/ai_nutrition/presentation/screens/meal_plan_detail_screen.dart';
import '../features/ai_nutrition/presentation/screens/meal_plan_screen.dart';
import '../features/ai_nutrition/presentation/screens/nutrition_screen.dart';
import '../features/auth/presentation/providers/auth_notifier.dart';
import '../features/auth/presentation/screens/otp_verify_screen.dart';
import '../features/auth/presentation/screens/phone_input_screen.dart';
import '../features/body_analysis/presentation/screens/body_analysis_screen.dart';
import '../features/body_analysis/presentation/screens/upload_photo_screen.dart';
import '../features/dashboard/presentation/screens/dashboard_screen.dart';
import '../features/diet/presentation/screens/diet_plan_screen.dart';
import '../features/diet/presentation/screens/meal_detail_screen.dart';
import '../features/diet/presentation/screens/meal_log_screen.dart';
import '../features/diet/data/models/diet_plan.dart';
import '../features/feedback/presentation/screens/feedback_form_screen.dart';
import '../features/profile/presentation/screens/membership_screen.dart';
import '../features/profile/presentation/screens/profile_screen.dart';
import '../features/progress/presentation/screens/progress_photos_screen.dart';
import '../features/progress/presentation/screens/progress_screen.dart';
import '../features/workouts/presentation/screens/workout_detail_screen.dart';
import '../features/workouts/presentation/screens/workout_list_screen.dart';
import '../features/workouts/presentation/screens/workout_log_screen.dart';
import '../features/workouts/data/models/workout_plan.dart';

/// App router with GoRouter, using auth state for redirects.
final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    initialLocation: '/',
    redirect: (context, state) {
      final isAuthenticated = authState.isAuthenticated;
      final isAuthRoute = state.matchedLocation == '/' ||
          state.matchedLocation == '/otp';

      if (!isAuthenticated && !isAuthRoute) {
        return '/'; // redirect to phone input
      }

      if (isAuthenticated && isAuthRoute) {
        return '/dashboard'; // redirect to dashboard
      }

      return null; // no redirect
    },
    routes: [
      GoRoute(
        path: '/',
        builder: (context, state) => const PhoneInputScreen(),
      ),
      GoRoute(
        path: '/otp',
        builder: (context, state) {
          final phone = state.extra as String? ?? '';
          return OtpVerifyScreen(phone: phone);
        },
      ),
      GoRoute(
        path: '/dashboard',
        builder: (context, state) => const DashboardScreen(),
      ),
      // Workouts
      GoRoute(
        path: '/workouts',
        builder: (context, state) => const WorkoutListScreen(),
      ),
      GoRoute(
        path: '/workouts/detail',
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>? ?? {};
          return WorkoutDetailScreen(
            plan: extra['plan'] as WorkoutPlan,
            day: extra['day'] as WorkoutDay,
          );
        },
      ),
      GoRoute(
        path: '/workouts/log',
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>? ?? {};
          return WorkoutLogScreen(
            plan: extra['plan'] as WorkoutPlan,
            day: extra['day'] as WorkoutDay,
          );
        },
      ),
      // Diet
      GoRoute(
        path: '/diet',
        builder: (context, state) => const DietPlanScreen(),
      ),
      GoRoute(
        path: '/diet/meals',
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>? ?? {};
          return MealDetailScreen(
            plan: extra['plan'] as DietPlan,
            day: extra['day'] as DietDay,
          );
        },
      ),
      GoRoute(
        path: '/diet/log',
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>? ?? {};
          return MealLogScreen(
            plan: extra['plan'] as DietPlan,
            day: extra['day'] as DietDay,
          );
        },
      ),
      // Attendance
      GoRoute(
        path: '/attendance',
        builder: (context, state) => const AttendanceHistoryScreen(),
      ),
      GoRoute(
        path: '/attendance/checkin',
        builder: (context, state) => const QrCheckInScreen(),
      ),
      // Progress
      GoRoute(
        path: '/progress',
        builder: (context, state) => const ProgressScreen(),
      ),
      GoRoute(
        path: '/progress/photos',
        builder: (context, state) => const ProgressPhotosScreen(),
      ),
      // Profile
      GoRoute(
        path: '/profile',
        builder: (context, state) => const ProfileScreen(),
      ),
      GoRoute(
        path: '/profile/membership',
        builder: (context, state) => const MembershipScreen(),
      ),
      // Feedback
      GoRoute(
        path: '/feedback',
        builder: (context, state) => const FeedbackFormScreen(),
      ),
      // AI Coach
      GoRoute(
        path: '/ai/coach',
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>? ?? {};
          return AiChatScreen(
            conversationId: extra['conversationId'] as int?,
          );
        },
      ),
      // Body Analysis
      GoRoute(
        path: '/body-analysis',
        builder: (context, state) => const BodyAnalysisScreen(),
      ),
      GoRoute(
        path: '/body-analysis/upload',
        builder: (context, state) => const UploadPhotoScreen(),
      ),
      // AI Nutrition
      GoRoute(
        path: '/nutrition',
        builder: (context, state) => const NutritionScreen(),
      ),
      GoRoute(
        path: '/nutrition/generate',
        builder: (context, state) => const MealPlanScreen(),
      ),
      GoRoute(
        path: '/nutrition/detail',
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>? ?? {};
          return MealPlanDetailScreen(
            plan: extra['plan'] as MealPlan,
          );
        },
      ),
    ],
  );
});
