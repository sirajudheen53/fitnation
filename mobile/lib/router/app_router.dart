import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/auth/presentation/providers/auth_notifier.dart';
import '../features/auth/presentation/screens/otp_verify_screen.dart';
import '../features/auth/presentation/screens/phone_input_screen.dart';
import '../features/dashboard/presentation/screens/dashboard_screen.dart';

/// App router with GoRouter, using auth state for redirects.
final routerProvider = Provider<GoRouter>((ref) {
  // Only re-create the router when authentication itself flips (login /
  // logout). Watching the full auth state would re-create it on transient
  // writes too (e.g. the loading toggles of a backend OTP request), which
  // resets navigation to the initial route mid-flow.
  final isAuthenticated = ref.watch(
    authProvider.select((state) => state.isAuthenticated),
  );

  return GoRouter(
    initialLocation: '/',
    redirect: (context, state) {
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
    ],
  );
});