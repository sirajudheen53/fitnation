import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/constants/app_constants.dart';

void main() {
  test('Firebase auth mode is the default', () {
    expect(AppConstants.authMode, AuthMode.firebase);
  });

  test('API base URL defaults to the production Cloud Run backend', () {
    expect(
      AppConstants.apiBaseUrl,
      'https://fitnation-backend-prod-6qezqfxxla-el.a.run.app',
    );
    expect(AppConstants.firebaseAuthEndpoint, '/auth/firebase/');
  });

  test('customer home endpoints are the self-scoped API paths (#95)', () {
    expect(AppConstants.attendanceListEndpoint, '/attendance/attendance/');
    expect(AppConstants.membershipsEndpoint, '/memberships/memberships/');
    expect(AppConstants.paymentsEndpoint, '/payments/');
    expect(AppConstants.pendingPaymentsStatus, 'pending');
  });
}
