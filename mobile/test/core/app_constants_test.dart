import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/constants/app_constants.dart';

void main() {
  test('Firebase auth mode is the default', () {
    expect(AppConstants.authMode, AuthMode.firebase);
  });

  test('API base URL falls back to the Android emulator loopback', () {
    expect(AppConstants.apiBaseUrl, 'http://10.0.2.2:8000');
    expect(AppConstants.firebaseAuthEndpoint, '/auth/firebase/');
  });
}
