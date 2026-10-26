import 'package:firebase_auth/firebase_auth.dart';

import '../../../../core/errors/failures.dart';

/// Maps a [FirebaseAuthException] to a user-friendly [Failure].
///
/// Covers the cases the owner called out: app not authorized (debug SHA not
/// registered in the Firebase console), too many attempts, quota exceeded,
/// invalid phone number, wrong/expired codes.
Failure mapFirebaseAuthException(FirebaseAuthException e) {
  switch (e.code) {
    // App / SHA not registered in the Firebase console, or Phone sign-in
    // provider disabled.
    case 'app-not-authorized':
    case 'invalid-api-key':
    case 'operation-not-allowed':
      return const AuthFailure(
        message:
            "Sign-in isn't set up for this app yet. "
            "Please contact support — the app needs to be registered "
            'for phone sign-in.',
        statusCode: 403,
      );

    case 'too-many-requests':
      return const AuthFailure(
        message:
            "We've received too many sign-in attempts from this device. "
            'Please try again later.',
        statusCode: 429,
      );

    case 'quota-exceeded':
      return const AuthFailure(
        message:
            'SMS quota for today has been exceeded. '
            'Please try again tomorrow or contact support.',
        statusCode: 429,
      );

    case 'invalid-phone-number':
      return const AuthFailure(
        message:
            "That phone number doesn't look right. "
            'Please check it and try again.',
        statusCode: 400,
      );

    case 'invalid-verification-code':
      return const AuthFailure(
        message:
            "That code is incorrect. Please double-check it and try again.",
        statusCode: 401,
      );

    case 'invalid-verification-id':
    case 'code-expired':
    case 'session-expired':
      return const AuthFailure(
        message:
            'This verification has expired. '
            'Please request a new code and try again.',
        statusCode: 401,
      );

    case 'network-request-failed':
      return const NetworkFailure();

    case 'user-disabled':
      return const AuthFailure(
        message: 'This account has been disabled. Please contact support.',
        statusCode: 403,
      );

    case 'missing-verification-code':
      return const AuthFailure(
        message: 'Please enter the 6-digit code from the SMS.',
        statusCode: 400,
      );

    default:
      return AuthFailure(
        message: e.message ?? 'Sign-in failed. Please try again.',
      );
  }
}

/// Backend contract for POST /auth/firebase/:
/// - 401 → invalid/expired Firebase ID token
/// - 429 → rate limited
/// - 4xx with gym-disambiguation payload → user must specify their gym
/// - 4xx other → validation
/// - 5xx → server config/delivery problem
Failure mapFirebaseBackendFailure(int? statusCode, Object? data) {
  final map = data is Map ? data : null;
  final detail = map?['detail']?.toString();

  final gyms = _parseGyms(map?['gyms']);
  final code = map?['code']?.toString();
  final isGymDisambiguation =
      gyms.isNotEmpty ||
      code == 'gym_required' ||
      code == 'gym_selection_required' ||
      code == 'tenant_ambiguity' ||
      code == 'tenant_required';

  if (statusCode != null && statusCode >= 400 && statusCode < 500) {
    if (isGymDisambiguation) {
      return TenantSelectionRequiredFailure(
        message: detail?.isNotEmpty == true
            ? detail!
            : 'Specify your gym to continue',
        gyms: gyms,
        statusCode: statusCode,
      );
    }
  }

  switch (statusCode) {
    case 401:
      return AuthFailure(
        message: detail?.isNotEmpty == true
            ? detail!
            : 'Your sign-in could not be verified. '
                  'Please start again and request a new code.',
        statusCode: statusCode,
      );
    case 403:
      return AuthFailure(
        message: detail?.isNotEmpty == true ? detail! : 'Sign-in is not allowed for this account. Please contact support.',
        statusCode: statusCode,
      );
    case 429:
      return const AuthFailure(
        message:
            'Too many sign-in attempts. Please wait a few minutes and '
            'try again.',
        statusCode: 429,
      );
    default:
      break;
  }

  if (statusCode != null && statusCode >= 500) {
    return ServerFailure(
      message:
          'We could not sign you in right now (server issue). '
          'Please try again shortly.',
      statusCode: statusCode,
    );
  }

  if (statusCode != null && statusCode >= 400) {
    return ValidationFailure(
      message: detail?.isNotEmpty == true
          ? detail!
          : 'Sign-in failed. '
                'Please check your details and try again.',
      errors: map?.cast<String, dynamic>() ?? const {},
      statusCode: statusCode,
    );
  }

  return UnknownFailure(message: detail ?? 'Sign-in failed. Please try again.');
}

List<GymOption> _parseGyms(Object? raw) {
  if (raw is! List) return const [];
  return raw.map(GymOption.fromJson).toList();
}
